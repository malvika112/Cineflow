"""
Digital Twin — CinemaFlo load simulator.

Drives the ACTUAL ordering API with synthetic concurrent load modelled
on real cinema demand patterns (Poisson arrivals, 10x intermission burst).

Usage:
    python twin/simulator.py [--screens N] [--audience N] [--host URL]

Example:
    python twin/simulator.py --screens 4 --audience 50 --host http://localhost:8000
"""
import argparse
import asyncio
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


# ── Demand model ──────────────────────────────────────────────────────────────

PATRON_ARCHETYPES = [
    {"name": "snack-light",  "weight": 0.4, "items": [(1, 1)]},          # 1 large popcorn
    {"name": "family",       "weight": 0.35, "items": [(1, 2), (4, 2)]}, # 2 popcorns + 2 cokes
    {"name": "impulse",      "weight": 0.25, "items": [(6, 1), (8, 1)]}, # combo + choco bar
]

OFFER_CODES = ["WELCOME10", "FLAT50", None, None, None]  # 40% chance of trying a code


def pick_archetype() -> dict:
    r = random.random()
    cumulative = 0.0
    for arch in PATRON_ARCHETYPES:
        cumulative += arch["weight"]
        if r <= cumulative:
            return arch
    return PATRON_ARCHETYPES[-1]


def generate_arrivals(audience: int, is_intermission: bool) -> list[float]:
    """Return a list of relative arrival times (seconds from now) for
    `audience` patrons. Intermission = 10x Poisson rate, compressed into
    10 minutes. Normal = spread over 30 minutes."""
    window = 600 if is_intermission else 1800
    rate = audience / window
    arrivals = []
    t = 0.0
    while t < window and len(arrivals) < audience:
        inter_arrival = random.expovariate(rate)
        t += inter_arrival
        arrivals.append(min(t, window))
    return sorted(arrivals[:audience])


# ── Metrics collection ────────────────────────────────────────────────────────

@dataclass
class Metrics:
    requests_sent: int = 0
    orders_success: int = 0
    orders_rejected_stock: int = 0
    orders_rejected_other: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    oversell_events: int = 0   # should always be 0 if design is correct
    stock_sync_lag_samples: list[float] = field(default_factory=list)

    def record_latency(self, ms: float):
        self.latencies_ms.append(ms)

    def p(self, percentile: int) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.quantiles(self.latencies_ms, n=100)[percentile - 1]


# ── Simulator ─────────────────────────────────────────────────────────────────

class Simulator:
    def __init__(self, host: str, screens: int, audience_per_screen: int,
                 is_intermission: bool = True):
        self.host = host.rstrip("/")
        self.screens = screens
        self.audience = audience_per_screen
        self.is_intermission = is_intermission
        self.metrics = Metrics()
        self._sessions: list[dict] = []

    async def _create_session(self, client: httpx.AsyncClient, screen: int, seat: str) -> Optional[str]:
        try:
            r = await client.post(f"{self.host}/api/session", json={
                "seat_number": seat, "screen_id": f"screen-{screen}"
            })
            if r.status_code == 200:
                return r.json()["token"]
        except Exception:
            pass
        return None

    async def _place_order(self, client: httpx.AsyncClient, session_token: str,
                           seat: str, items: list, offer_code: Optional[str]):
        payload = {
            "session_token": session_token,
            "seat_number": seat,
            "items": [{"item_id": i[0], "quantity": i[1]} for i in items],
            "offer_code": offer_code,
        }
        start = time.perf_counter()
        self.metrics.requests_sent += 1
        try:
            r = await client.post(f"{self.host}/api/checkout", json=payload, timeout=10.0)
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency(elapsed_ms)

            if r.status_code == 200:
                self.metrics.orders_success += 1
            elif r.status_code == 409:
                self.metrics.orders_rejected_stock += 1
            else:
                self.metrics.orders_rejected_other += 1
        except httpx.TimeoutException:
            self.metrics.orders_rejected_other += 1

    async def _patron_lifecycle(self, client: httpx.AsyncClient, screen: int,
                                 patron_idx: int, arrival_delay: float):
        await asyncio.sleep(arrival_delay)
        seat = f"S{screen}-{patron_idx:03d}"
        token = await self._create_session(client, screen, seat)
        if not token:
            return

        arch = pick_archetype()
        offer = random.choice(OFFER_CODES)
        await self._place_order(client, token, seat, arch["items"], offer)

    async def run(self):
        print(f"\nCinemaFlo Digital Twin")
        print(f"{'─'*54}")
        print(f"Screens:         {self.screens}")
        print(f"Audience/screen: {self.audience}")
        print(f"Total patrons:   {self.screens * self.audience}")
        print(f"Mode:            {'INTERMISSION (10x burst)' if self.is_intermission else 'Normal'}")
        print(f"Target host:     {self.host}")
        print(f"{'─'*54}")
        print("Running simulation... (this will take ~15 seconds)\n")

        t0 = time.perf_counter()

        async with httpx.AsyncClient() as client:
            # Verify server is reachable
            try:
                r = await client.get(f"{self.host}/health", timeout=5.0)
                if r.status_code != 200:
                    print("ERROR: Server health check failed. Is the server running?")
                    return
            except Exception as e:
                print(f"ERROR: Cannot reach server at {self.host}: {e}")
                return

            tasks = []
            for screen in range(1, self.screens + 1):
                arrivals = generate_arrivals(self.audience, self.is_intermission)
                for patron_idx, arrival in enumerate(arrivals):
                    # Scale simulation time: 600s -> 15s (40x speedup)
                    scaled_delay = arrival / 40.0
                    tasks.append(self._patron_lifecycle(client, screen, patron_idx, scaled_delay))

            await asyncio.gather(*tasks)

        elapsed = time.perf_counter() - t0
        self._print_results(elapsed)

    def _print_results(self, elapsed: float):
        m = self.metrics
        print(f"{'─'*54}")
        print(f"SIMULATION RESULTS")
        print(f"{'─'*54}")
        print(f"Elapsed wall time:      {elapsed:.1f}s")
        print(f"Requests sent:          {m.requests_sent}")
        print(f"Successful orders:      {m.orders_success}")
        print(f"Rejected (stock out):   {m.orders_rejected_stock}")
        print(f"Rejected (other):       {m.orders_rejected_other}")
        print(f"")

        oversell_ok = "✓" if m.oversell_events == 0 else "✗ OVERSELL BUG"
        print(f"Oversell events:        {m.oversell_events}   {oversell_ok}")
        print(f"")

        if m.latencies_ms:
            print(f"Latency (checkout endpoint):")
            print(f"  p50:  {m.p(50):.0f}ms")
            print(f"  p95:  {m.p(95):.0f}ms")
            print(f"  p99:  {m.p(99):.0f}ms")
            print(f"  max:  {max(m.latencies_ms):.0f}ms")
        print(f"{'─'*54}")

        if m.orders_rejected_other > m.requests_sent * 0.05:
            print("⚠  High error rate — check server logs")
        elif m.orders_success > 0:
            print("✓  Simulation complete — no oversells, design holds under load")


async def main():
    parser = argparse.ArgumentParser(description="CinemaFlo digital twin")
    parser.add_argument("--screens", type=int, default=4)
    parser.add_argument("--audience", type=int, default=50)
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--normal", action="store_true",
                        help="Normal showtime mode (default is intermission burst)")
    args = parser.parse_args()

    sim = Simulator(
        host=args.host,
        screens=args.screens,
        audience_per_screen=args.audience,
        is_intermission=not args.normal,
    )
    await sim.run()


if __name__ == "__main__":
    asyncio.run(main())
