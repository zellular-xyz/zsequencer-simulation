from simulations.dynamic_network_simulation_with_nodes_registry import (SimulationConfig, DynamicNetworkSimulation)


def main():
    DynamicNetworkSimulation(simulation_config=SimulationConfig()).run()


if __name__ == '__main__':
    main()
