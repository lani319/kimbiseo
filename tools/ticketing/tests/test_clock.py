import math

import pytest

from ticketing.clock import intersect, measure, sleep_until


class FakeServer:
    """Fake clock + server whose clock is local + true_offset."""

    def __init__(self, true_offset: float, rtt: float, start: float = 1_700_000_000.3):
        self.t, self.true_offset, self.rtt = start, true_offset, rtt

    def now(self):
        return self.t

    async def sleep(self, dt):
        self.t += dt

    async def fetch(self):
        t0 = self.t
        self.t += self.rtt
        return t0, self.t, math.floor(t0 + self.rtt / 2 + self.true_offset)  # stamped mid-flight


@pytest.mark.parametrize("true_offset", [-2.35, -0.4, 0.0, 0.42, 3.999])
async def test_measure_converges(true_offset):
    srv = FakeServer(true_offset, rtt=0.03)
    off = await measure(srv.fetch, samples=10, now=srv.now, sleep=srv.sleep)
    assert off.lo <= true_offset <= off.hi
    assert off.error < 0.02
    assert abs(off.value - true_offset) < 0.02


def test_single_sample_is_one_second_wide():
    off = intersect([(100.0, 100.0, 105)])
    assert (off.lo, off.hi) == (5.0, 6.0)


def test_inconsistent_samples_fall_back_to_best_rtt():
    off = intersect([(100.0, 100.01, 105), (101.0, 101.2, 200)])
    assert off.lo <= off.hi
    assert 4.0 < off.value < 6.0


def test_intersect_requires_samples():
    with pytest.raises(ValueError):
        intersect([])


async def test_sleep_until_returns_at_target():
    t = {"now": 1000.0}

    def now():
        return t["now"]

    async def fake_sleep(dt):
        t["now"] += max(dt, 0.001)

    import ticketing.clock as c

    orig = c.asyncio.sleep
    c.asyncio.sleep = fake_sleep
    try:
        await sleep_until(1010.0, offset=2.0, now=now)  # server = local + 2
    finally:
        c.asyncio.sleep = orig
    assert 1008.0 <= t["now"] < 1008.01
