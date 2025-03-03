import json

import simulations.utils as simulations_utils
from simulations.config import SimulationConfig
from simulations.schema import ExecutionData

NETWORK_NODES_COUNT = 4


def main(network_nodes_num=NETWORK_NODES_COUNT):
    simulation_conf = SimulationConfig(ZSEQUENCER_NODES_SOURCE="file")

    sequencer_address, network_keys = simulations_utils.generate_network_keys(network_nodes_num=network_nodes_num)

    nodes_execution_args = {}
    nodes_info = {}
    for idx, key_data in enumerate(network_keys):
        simulation_conf.prepare_node(node_idx=idx, keys=key_data.keys)
        nodes_info[key_data.address] = simulations_utils.generate_node_info(node_idx=idx, key_data=key_data).dict()
        nodes_execution_args[key_data.address] = ExecutionData(
            execution_cmd=simulations_utils.generate_node_execution_command(idx),
            env_variables=simulation_conf.to_dict(node_idx=idx, sequencer_initial_address=sequencer_address))

    with open(simulation_conf.nodes_file, "w") as file:
        json.dump(nodes_info, file, indent=4)

    with open(simulation_conf.apps_file, "w") as file:
        json.dump(simulations_utils.APPS, file, indent=4)

    for _, execution_data in nodes_execution_args.items():
        simulations_utils.bootstrap_node(env_variables=execution_data.env_variables,
                                         node_execution_cmd=execution_data.execution_cmd)


if __name__ == "__main__":
    main()
