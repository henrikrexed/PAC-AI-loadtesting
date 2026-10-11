# shape.py — LoadTestShape base: the OPEN-ARRIVAL approximation (G-O1).
#
# Locust is closed / user-native: it controls the number of CONCURRENT USERS, not
# an arrival rate. The §4 arrivalProfile (model=open) gives a per-stage target
# iterations/s. We approximate it with a step-wise LoadTestShape whose user count
# per stage is derived from Little's Law (users = rate x mean-service-time, taken
# from arrivalProfile.littlesLawCheck.expectedConcurrency) and a per-task pacing
# (`constant_pacing` on the User) tuned so each user issues ~1/mean-service-time
# iterations/s. The aggregate then tracks the open-model target. This is an
# APPROXIMATION — the generated supports() declares it so the agent warns the human
# at VALIDATE. The generated locustfile subclasses StagedShape and sets `stages`.

from locust import LoadTestShape


class StagedShape(LoadTestShape):
    """Step-wise shape driven by a precomputed stage table. Each stage is
    {"end_s": float, "users": int, "spawn_rate": float}; `end_s` is the cumulative
    end time of the stage. Holds the Little's-Law user count for each window and
    stops when the schedule is exhausted (terminal ramp-down to 0 users, G3)."""

    stages = []

    def tick(self):
        run_time = self.get_run_time()
        for st in self.stages:
            if run_time < st["end_s"]:
                return (int(st["users"]), max(0.1, float(st["spawn_rate"])))
        return None
