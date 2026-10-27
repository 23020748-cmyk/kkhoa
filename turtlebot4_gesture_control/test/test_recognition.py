from turtlebot4_gesture_control.recognition import WaveDetector
from turtlebot4_gesture_control.protocol import decode, Encoder
import pytest
import json


def test_wave_needs_two_reversals():
    d = WaveDetector()
    xs = [.4, .48, .56, .64, .55, .46, .38, .46, .55, .64]
    results = [d.update(x, .5, i*.08) for i, x in enumerate(xs)]
    assert not any(results[:7])
    assert any(results[7:])


def test_stationary_palm_and_jitter_are_not_wave():
    d = WaveDetector()
    assert not any(d.update(.5+(.008 if i % 2 else 0), .5, i*.08) for i in range(100))


def test_wave_resets_on_gap_vertical_change_and_hand_change():
    d = WaveDetector()
    for i, x in enumerate([.4,.6,.4,.6]):
        d.update(x,.5,i*.2)
    assert not d.update(.5,.5,2.)
    assert not d.update(.5,.9,2.1)
    assert not d.update(.6,.9,2.2,'Left')


def test_contract_roundtrip():
    d = decode(Encoder().encode('VICTORY', .9))
    assert d['label'] == 'VICTORY'


@pytest.mark.parametrize('raw', ['WAVE', '{"v":1,"label":"HACK"}', '[]',
                               '{"v":1,"label":"WAVE","confidence":NaN}'])
def test_unknown_or_invalid_message(raw):
    with pytest.raises((ValueError, TypeError)):
        decode(raw)


def test_stale_and_nan_rejected():
    d = json.loads(Encoder().encode('WAVE', .9))
    d['stamp'] -= 5
    with pytest.raises(ValueError):
        decode(json.dumps(d))
    d['confidence'] = float('nan')
    with pytest.raises(ValueError):
        decode(json.dumps(d))
