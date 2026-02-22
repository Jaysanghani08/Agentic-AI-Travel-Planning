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
    def intent_analysis(self) -> Task:
        return Task(config=self.tasks_config["intent_analysis"])  # type: ignore[index]

    @task
    def research_discovery(self) -> Task:
        return Task(
            config=self.tasks_config["research_discovery"],  # type: ignore[index]
            human_input=False,  # HITL is handled in the UI; no terminal prompt
        )

    @task
    def logistics_sourcing(self) -> Task:
        return Task(config=self.tasks_config["logistics_sourcing"])  # type: ignore[index]

    @task
    def audit_optimization(self) -> Task:
        return Task(config=self.tasks_config["audit_optimization"])  # type: ignore[index]

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    def scout_crew(self) -> Crew:
        """Run only intent_analysis + research_discovery to get shortlist for UI approval."""
        return Crew(
            agents=[self.orchestrator(), self.scout()],
            tasks=[self.intent_analysis(), self.research_discovery()],
            process=Process.sequential,
            verbose=True,
        )

    def logistics_crew(self) -> Crew:
        """Run logistics + audit after user approves shortlist in UI. Needs shortlist_from_scout and human_approval in kickoff inputs."""
        return Crew(
            agents=[self.logistician(), self.auditor()],
            tasks=[self.logistics_sourcing(), self.audit_optimization()],
            process=Process.sequential,
            verbose=True,
        )
