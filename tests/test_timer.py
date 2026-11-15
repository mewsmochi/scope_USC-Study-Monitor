from sessions.timer import pomodoro_phase


def test_pomodoro_phase():
    assert pomodoro_phase(0, 1500, 300, 4) == ("work", 1, 1500)
    assert pomodoro_phase(1500, 1500, 300, 4) == ("break", 1, 300)
    assert pomodoro_phase(1800, 1500, 300, 4) == ("work", 2, 1500)
    assert pomodoro_phase(6899, 1500, 300, 4) == ("work", 4, 1)
    assert pomodoro_phase(6900, 1500, 300, 4) == ("done", 4, 0)   # no break after the last round
