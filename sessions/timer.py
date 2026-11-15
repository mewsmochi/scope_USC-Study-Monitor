"""Pomodoro math. Pure function of elapsed time so it's easy to test."""


def pomodoro_phase(elapsed, work, brk, rounds):
    """Returns (phase, round_number, seconds_left_in_phase).

    phase is "work", "break", or "done". There's no break after the last round.
    """
    cycle = work + brk
    if elapsed >= rounds * cycle - brk:
        return "done", rounds, 0
    rnd, into = divmod(elapsed, cycle)
    if into < work:
        return "work", int(rnd) + 1, work - into
    return "break", int(rnd) + 1, cycle - into
