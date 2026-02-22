"""Travel Agent System crew - sequential workflow with Scout, Logistician, Auditor, Orchestrator."""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List


@CrewBase
class TravelAgentSystemCrew:
    """Multi-agent travel system: research -> logistics -> audit -> orchestration."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def scout(self) -> Agent:
        return Agent(
            config=self.agents_config["scout"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def logistician(self) -> Agent:
        return Agent(
            config=self.agents_config["logistician"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def auditor(self) -> Agent:
        return Agent(
            config=self.agents_config["auditor"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def orchestrator(self) -> Agent:
        return Agent(
            config=self.agents_config["orchestrator"],  # type: ignore[index]
            verbose=True,
        )

    @task
    def scout_research(self) -> Task:
        return Task(config=self.tasks_config["scout_research"])  # type: ignore[index]

    @task
    def logistician_fetch(self) -> Task:
        return Task(config=self.tasks_config["logistician_fetch"])  # type: ignore[index]

    @task
    def auditor_validate(self) -> Task:
        return Task(config=self.tasks_config["auditor_validate"])  # type: ignore[index]

    @task
    def orchestrator_review(self) -> Task:
        return Task(config=self.tasks_config["orchestrator_review"])  # type: ignore[index]

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
