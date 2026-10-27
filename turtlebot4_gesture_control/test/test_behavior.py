import pytest
from turtlebot4_gesture_control.behavior import Controller, Config


def feed(c, label, start=0., seconds=0.4, score=0.95):
    velocity = None
    for i in range(round(seconds/0.05)+1):
        velocity = c.receive(label, score, start+i*0.05)
    return velocity


def running(label='POINTING_UP'):
    c = Controller()
    feed(c, label)
    feed(c, 'THUMBS_UP', 0.45)
    assert c.state == 'EXECUTING'
    return c


def test_selection_requires_confirmation():
    c = Controller()
    assert feed(c, 'WAVE') == (0., 0.)
    assert c.state == 'SELECTED'
    assert c.selected == 'GREETING'


def test_thumb_without_selection():
    c = Controller()
    feed(c, 'NO_HAND', seconds=0.3)
    assert feed(c, 'THUMBS_UP', 0.35) == (0., 0.)
    assert c.state != 'EXECUTING'


def test_four_complete_cycles_and_no_repeating_held_thumb():
    c = running()
    assert len(c.plan) == 8
    assert [p[0] for p in c.plan] == [0.08, -0.08]*4
    visited = {c.index}
    for i in range(1, 350):
        now = 0.85+i*0.05
        velocity = c.receive('THUMBS_UP', .99, now)
        visited.add(c.index)
    assert set(range(8)) <= visited
    assert c.reason == 'completed'
    assert c.state == 'IDLE'
    assert c.selected is None
    assert velocity == (0., 0.)


def test_immediate_palm_stop_requires_new_confirmation():
    c = running()
    assert c.receive('OPEN_PALM', .46, .9) == (0., 0.)
    assert c.state == 'STOPPED'
    feed(c, 'THUMBS_UP', .95, seconds=1)
    assert c.state == 'STOPPED'
    feed(c, 'VICTORY', 2.0)
    assert feed(c, 'THUMBS_UP', 2.45) != (0., 0.)


def test_wave_during_execution_is_stop():
    c = running()
    assert c.receive('WAVE', .95, .9) == (0., 0.)
    assert c.state == 'STOPPED'


def test_fist_cancels_and_clears():
    c = running()
    assert c.receive('CLOSED_FIST', .5, .9) == (0., 0.)
    assert c.state == 'CANCELLED' and c.selected is None
    feed(c, 'VICTORY', 1.)
    feed(c, 'CLOSED_FIST', 1.45)
    assert c.selected is None


@pytest.mark.parametrize('label', ['NO_HAND', 'UNKNOWN'])
def test_hand_timeout(label):
    c = running()
    feed(c, label, .9, seconds=.8)
    assert c.state == 'STOPPED'
    assert c.reason == 'hand_timeout'


def test_heartbeat_timeout():
    c = running()
    assert c.tick(1.6) == (0., 0.)
    assert c.reason == 'heartbeat_timeout'
    feed(c, 'THUMBS_UP', 1.65)
    assert c.state == 'STOPPED'


def test_noise_no_movement():
    c = Controller()
    for i in range(50):
        assert c.receive(['VICTORY', 'POINTING_UP', 'THUMBS_UP'][i % 3], .99, i*.05) == (0., 0.)
    assert c.selected is None
    assert feed(c, 'VICTORY', 3, score=.5) == (0., 0.)
    assert c.selected is None


def test_shutdown_exception_and_camera_error():
    for reason in ['shutdown', 'exception']:
        c = running()
        assert c.stop(reason) == (0., 0.)
        assert c.tick(.9) == (0., 0.)
    c = running()
    assert c.receive('CAMERA_ERROR', 0., .9) == (0., 0.)


@pytest.mark.parametrize('label', ['WAVE', 'VICTORY'])
def test_all_behaviors_complete_zero(label):
    c = running(label)
    for i in range(900):
        c.receive('THUMBS_UP', .99, .9+i*.05)
    assert c.state == 'IDLE' and c.tick(45.9) == (0., 0.)


def test_timer_stall_stops():
    c = running()
    assert c.receive('THUMBS_UP', .99, 1.2) == (0., 0.)
    assert c.reason == 'timer_stall'


@pytest.mark.parametrize('kwargs', [dict(linear_speed=1.), dict(circle_radius=0.), dict(cycles=0),
                                    dict(segment_seconds=float('nan')), dict(cycles=2.5)])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_short_unknown_gap_preserves_confirmation_but_noise_alone_cannot_confirm():
    c = Controller()
    feed(c, 'POINTING_UP')
    c.receive('THUMBS_UP', .95, .45)
    c.receive('THUMBS_UP', .95, .55)
    c.receive('UNKNOWN', .2, .6)
    assert c.state == 'SELECTED'
    assert c.receive('THUMBS_UP', .95, .75) != (0., 0.)
    assert c.state == 'EXECUTING'


def test_long_unknown_gap_resets_confirmation():
    c = Controller()
    feed(c, 'POINTING_UP')
    c.receive('THUMBS_UP', .95, .45)
    feed(c, 'UNKNOWN', .5, seconds=.25)
    assert c.receive('THUMBS_UP', .95, .8) == (0., 0.)
    assert c.state != 'EXECUTING'


def test_held_palm_releases_thumb_without_resuming():
    c = running()
    assert feed(c, 'OPEN_PALM', .9, seconds=.4) == (0., 0.)
    assert c.state == 'STOPPED'
    assert c.armed
    assert feed(c, 'THUMBS_UP', 1.35) != (0., 0.)
    assert c.state == 'EXECUTING'
