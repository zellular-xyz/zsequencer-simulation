from simulations.dynamic_network_simulation_with_nodes_registry import (SimulationConfig, DynamicNetworkSimulation)
from examples.orchestrator import orchestrate_simulation


def main():
    orchestrate_simulation()
    # DynamicNetworkSimulation(simulation_config=SimulationConfig()).run()


if __name__ == '__main__':
    main()
