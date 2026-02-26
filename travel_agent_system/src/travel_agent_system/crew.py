"""Travel Agent System crew - sequential workflow with Scout, Logistician, Auditor, Orchestrator."""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

from travel_agent_system.tools.amadeus_tools import flight_search_tool, hotel_search_tool


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
            tools=[flight_search_tool, hotel_search_tool],
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

    @task
    def itinerary_generation(self) -> Task:
        return Task(config=self.tasks_config["itinerary_generation"])  # type: ignore[index]

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    def scout_crew(self) -> Crew:
        """Run only research_discovery; trip context is passed via kickoff inputs."""
        return Crew(
            agents=[self.scout()],
            tasks=[self.research_discovery()],
            process=Process.sequential,
            verbose=True,
        )

    def logistics_only_crew(self, verbose: bool = True) -> Crew:
        """Run only logistics_sourcing so the logistics plan (with booking links) can be captured and shown to the user."""
        return Crew(
            agents=[self.logistician()],
            tasks=[self.logistics_sourcing()],
            process=Process.sequential,
            verbose=verbose,
        )

    def audit_only_crew(self, verbose: bool = True) -> Crew:
        """Run only audit_optimization; requires logistics_plan_from_previous_step in kickoff inputs."""
        return Crew(
            agents=[self.auditor()],
            tasks=[self.audit_optimization()],
            process=Process.sequential,
            verbose=verbose,
        )

    def itinerary_crew(self, verbose: bool = True) -> Crew:
        """Synthesize activities, logistics, and audit into a day-by-day itinerary."""
        return Crew(
            agents=[self.orchestrator()],
            tasks=[self.itinerary_generation()],
            process=Process.sequential,
            verbose=verbose,
        )
