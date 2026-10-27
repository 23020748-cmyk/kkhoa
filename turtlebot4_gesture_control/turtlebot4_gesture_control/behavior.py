"""Pure, nonblocking controller; monotonic wall time, no ROS dependencies."""
from dataclasses import dataclass
import math


@dataclass
class Config:
    linear_speed: float = 0.08
    angular_speed: float = 0.35
    segment_seconds: float = 1.5
    greeting_seconds: float = 1.0
    circle_radius: float = 0.4
    cycles: int = 4
    heartbeat_timeout: float = 0.7
    no_hand_timeout: float = 0.6
    debounce_seconds: float = 0.25
    debounce_frames: int = 3
    noise_grace_seconds: float = 0.15
    release_seconds: float = 0.2
    cooldown_seconds: float = 0.7
    max_tick_gap: float = 0.3
    confidence: float = 0.65
    stop_confidence: float = 0.45

    def __post_init__(self):
        for key, value in vars(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{key} must be finite and positive')
        if type(self.cycles) is not int or type(self.debounce_frames) is not int:
            raise ValueError('cycles/debounce_frames must be integers')
        if self.linear_speed > 0.15 or self.angular_speed > 0.6:
            raise ValueError('speed exceeds coursework safety limits')
        if self.circle_radius < 0.25 or self.circle_radius > 0.8:
            raise ValueError('radius outside validated arena bounds')
        if self.linear_speed * self.segment_seconds > 0.5:
            raise ValueError('straight segment exceeds 0.5 m')
        if self.confidence > 1 or self.stop_confidence > self.confidence:
            raise ValueError('invalid confidence thresholds')


class Controller:
    SELECT = {'WAVE': 'GREETING', 'POINTING_UP': 'BACK_AND_FORTH', 'VICTORY': 'CIRCLE'}

    def __init__(self, config=None):
        self.c = config or Config()
        self.state, self.selected, self.reason = 'IDLE', None, 'startup'
        self.last_heartbeat = self.last_hand = None
        self.candidate, self.candidate_since, self.count = None, 0., 0
        self.latched = None
        self.release_since = None
        self.armed = False
        self.cooldown_until = 0.
        self.plan, self.index, self.segment_start = [], 0, 0.
        self.last_tick = None
        self.noise_since = None

    def stop(self, reason, clear=False):
        self.plan = []
        self.index = 0
        self.state = 'CANCELLED' if clear else 'STOPPED'
        self.reason = reason
        if clear:
            self.selected = None
        # No auto-resume: require a stable release then a new thumbs-up.
        self.armed = False
        self.release_since = None
        self.candidate, self.count = None, 0
        return (0., 0.)

    def receive(self, label, confidence, now):
        self.last_heartbeat = now
        if label == 'CAMERA_ERROR':
            return self.stop('camera_error')
        if label in ('NO_HAND', 'UNKNOWN') or confidence < self.c.stop_confidence:
            label = 'NO_HAND'
        else:
            self.last_hand = now
        # Stop immediately, without the selection debounce window.
        # WAVE is also a moving open palm; never ignore it during execution.
        if label == 'OPEN_PALM' or (label == 'WAVE' and self.state == 'EXECUTING'):
            # A held palm remains a stop, but also counts as releasing the thumb.
            # Otherwise a harmless palm during the pose transition can deadlock confirm.
            release = self.release_since if (self.state == 'STOPPED' and
                      self.reason == 'open_palm' and self.release_since is not None) else now
            velocity = self.stop('open_palm')
            self.release_since = release
            self.armed = now-release >= self.c.release_seconds
            if self.armed:
                self.latched = None
            return velocity
        if label == 'CLOSED_FIST':
            return self.stop('closed_fist', clear=True)
        if label != 'THUMBS_UP':
            if self.release_since is None:
                self.release_since = now
            if now - self.release_since >= self.c.release_seconds:
                self.armed = True
                self.latched = None
        else:
            self.release_since = None
        if label == 'NO_HAND' or confidence < self.c.confidence:
            if self.noise_since is None:
                self.noise_since = now
            if now-self.noise_since > self.c.noise_grace_seconds:
                self.candidate, self.count = None, 0
            return self.tick(now)
        self.noise_since = None
        if label != self.candidate:
            self.candidate, self.candidate_since, self.count = label, now, 1
        else:
            self.count += 1
        stable = self.count >= self.c.debounce_frames and now - self.candidate_since >= self.c.debounce_seconds
        if stable and label != self.latched and now >= self.cooldown_until:
            self.latched = label
            if self.state != 'EXECUTING' and label in self.SELECT:
                self.selected = self.SELECT[label]
                self.state, self.reason = 'SELECTED', 'await_thumbs_up'
            elif label == 'THUMBS_UP' and self.armed:
                self.armed = False
                if self.selected and self.state in ('SELECTED', 'STOPPED'):
                    self._start(now)
        return self.tick(now)

    def _start(self, now):
        c = self.c
        if self.selected == 'GREETING':
            self.plan = [(0., c.angular_speed, c.greeting_seconds),
                         (0., -c.angular_speed, 2*c.greeting_seconds),
                         (0., c.angular_speed, c.greeting_seconds)]
        elif self.selected == 'BACK_AND_FORTH':
            # Four complete cycles = forward AND backward, eight moving segments.
            self.plan = [(v, 0., c.segment_seconds)
                         for _ in range(c.cycles) for v in (c.linear_speed, -c.linear_speed)]
        else:
            self.plan = [(c.linear_speed, c.linear_speed/c.circle_radius,
                          2*math.pi*c.circle_radius/c.linear_speed)]
        self.state, self.reason = 'EXECUTING', 'confirmed'
        self.index, self.segment_start = 0, now
        self.last_tick = now
        self.cooldown_until = now + c.cooldown_seconds

    def tick(self, now):
        if self.last_heartbeat is None or now - self.last_heartbeat > self.c.heartbeat_timeout:
            return self.stop('heartbeat_timeout')
        if self.last_hand is None or now - self.last_hand > self.c.no_hand_timeout:
            return self.stop('hand_timeout')
        if self.state != 'EXECUTING':
            return (0., 0.)
        if self.last_tick is not None and now - self.last_tick > self.c.max_tick_gap:
            return self.stop('timer_stall')
        self.last_tick = now
        if now - self.segment_start >= self.plan[self.index][2]:
            self.index += 1
            self.segment_start = now
            if self.index >= len(self.plan):
                self.plan = []
                self.selected = None
                self.state, self.reason = 'IDLE', 'completed'
                self.armed = False
                self.release_since = None
                return (0., 0.)
            # One zero-command tick between direction changes.
            return (0., 0.)
        return self.plan[self.index][:2]

    def status(self):
        return dict(state=self.state, selected=self.selected, reason=self.reason,
                    segment=self.index, segments=len(self.plan), armed=self.armed)
