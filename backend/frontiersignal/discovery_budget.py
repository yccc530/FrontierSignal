"""Explicit, durable GitHub budgets; credentials never select a larger budget."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import WorkbenchState


class DiscoveryBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    github_queries_per_run: int = Field(2, ge=1, le=4)
    github_candidates_per_query: int = Field(10, ge=1, le=30)
    github_track_per_run: int = Field(10, ge=1, le=15)
    github_code_checks: int = Field(3, ge=0, le=10)
    github_readme_checks: int = Field(2, ge=0, le=5)
    github_history_checks: int = Field(8, ge=0, le=15)
    github_search_pages: int = Field(3, ge=1, le=5)
    github_mature_queries: int = Field(0, ge=0, le=2)
    github_organization_queries: int = Field(0, ge=0, le=2)
    github_fixed_per_run: int = Field(0, ge=0, le=10)

    @model_validator(mode="after")
    def reserve_growth(self):
        if (
            self.github_mature_queries + self.github_organization_queries
            >= self.github_queries_per_run
        ):
            raise ValueError("总查询预算须至少给原有增长主题保留 1 组")
        if self.github_fixed_per_run > self.github_track_per_run:
            raise ValueError("固定仓库轮换数不能超过总跟踪名额")
        return self


def current_budget(config):
    return DiscoveryBudget.model_validate(
        {key: getattr(config, key) for key in DiscoveryBudget.model_fields}
    )


async def load_discovery_budget(db, config):
    async with db.sessions() as session:
        stored = await session.get(WorkbenchState, "discovery-budget")
        if stored:
            value = DiscoveryBudget.model_validate(stored.value)
            return config.model_copy(update=value.model_dump())
    return config


def public_budget(config):
    value = current_budget(config)
    data = value.model_dump()
    # A 304 does not download a body, but still consumes a logical request slot.
    data["max_requests"] = (
        value.github_queries_per_run
        + 2 * value.github_track_per_run
        + value.github_code_checks
        + value.github_readme_checks
        + value.github_history_checks
    )
    data["growth_queries"] = (
        value.github_queries_per_run
        - value.github_mature_queries
        - value.github_organization_queries
    )
    data["fixed_within_tracking_budget"] = True
    data["credential_auto_increase"] = False
    return data
