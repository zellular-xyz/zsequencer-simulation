# Dispute and Switch Scenarios  

## Overview  
This project includes simulations for handling dispute and leader-switching scenarios in a distributed network.  

## Scenarios  

### **Leader Failure Simulation**  

#### **Description**  
This simulation tests the system’s ability to handle the failure of a leader node and verify if the network can synchronize new batches.  

#### **Steps to Run the Simulation**  

1. Run the following command to start the simulation:  

    ```bash
    python -m simulations.dispute_and_switch.without_proxy_file_source
    ```  

2. This will:  
   - Launch a network with four nodes in separate terminals.  
   - Print a sorted list of nodes (address, socket) to verify the leader sequence.  

3. **Before sending dummy batches**, check the `URL` variable in the `stress_test.stress_test` script and set it to a valid URL. Some nodes may be down, so ensure the URL points to an active node.  

4. To send dummy batches to the network (excluding the leader), use the following script:  

    ```bash
    python -m stress_test.stress_test
    ```  

5. Manually terminate the sequencer process based on the printed priority list.  

6. Restart the sequencer process and verify if the nodes can sync with newly sequenced batches.  

## **Additional Notes**  
- The leader does not accept batches from clients.  
- Nodes should automatically adjust to the leader failure and continue processing new batches.  

