# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/simulator.ipynb.

# %% auto 0
__all__ = ['Simulator']

# %% ../nbs/simulator.ipynb 1
from dataclasses import dataclass
from typing import Callable
from bayesianfin.data import FeatureEngineer, append_from_log_ret
from jax import random
from numpyro.infer import Predictive
import numpy.typing as npt
import polars as pl
from tqdm import tqdm
import random as pyrandom

# %% ../nbs/simulator.ipynb 2
@dataclass
class Simulator:
    model: Callable
    feature_engineer: FeatureEngineer
    target_site: str = "log_ret"
    inherit_vals: list[str] = ()
    exo_fixed_effects: list[str] = ()
    additional_effects: list[str] = ()

    def simulate_paths(
        self,
        steps: int,
        starting_sim_df: pl.DataFrame,
        posterior_samples: dict[str, npt.NDArray],
        num_sims: int = 10,
    ) -> pl.DataFrame:
        all_trajectories = []
        for sim_id in range(num_sims):
            simulated_path = self.simulate_path(
                steps=steps,
                starting_sim_df=starting_sim_df,
                posterior_samples=posterior_samples,
            )
            all_trajectories.append(simulated_path.with_columns(run_id=pl.lit(sim_id)))
        all_runs = pl.concat(all_trajectories)
        return all_runs

    def simulate_path(
        self,
        steps: int,
        starting_sim_df: pl.DataFrame,
        posterior_samples: dict[str, npt.NDArray],
    ):
        rng_key = random.PRNGKey(pyrandom.randint(0, 1024))
        rng_key, sim_key = random.split(rng_key)
        sim_key, traj_key = random.split(sim_key)
        feature_engineer = self.feature_engineer
        prior_predictive = Predictive(
            self.model,
            posterior_samples=posterior_samples,
            num_samples=1,
        )
        feature_sim_df = feature_engineer.create_features(starting_sim_df)
        current_price_shifts = feature_engineer.to_numpy_dict(feature_sim_df[-1])

        add_kwargs = {}
        for eff in self.exo_fixed_effects:
            add_kwargs[eff] = feature_sim_df[-1][eff].to_numpy()

        for t in range(steps):
            traj_key, step_key = random.split(traj_key)
            prior_predictions = prior_predictive(
                step_key, past_values=current_price_shifts, **add_kwargs
            )
            # Takes any samples from the site and record it
            new_log_ret = prior_predictions[self.target_site].squeeze().item()
            starting_sim_df = append_from_log_ret(
                starting_sim_df,
                new_log_ret=new_log_ret,
                inherit_vals=self.inherit_vals,
                add_variables={
                    e: int(prior_predictions[e].squeeze().item())
                    for e in self.additional_effects
                },
            )

            # With the new record attached, we re-extract the features.
            feature_sim_df = feature_engineer.create_features(starting_sim_df)
            current_price_shifts = feature_engineer.to_numpy_dict(feature_sim_df[-1])

        return starting_sim_df

