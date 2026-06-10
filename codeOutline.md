## Flight Stages  
1) Power on - T-2hrs from launch: Craft power turns on
2) Seperation/Boost T+60-63 min from launch: Spaceship seperates from launcher craft, boosts to feather position 
3) Z-Grav T+63 min from launch: Begin of 3 minute microgravity phase 
4) Reentry T+66 min from launch: microgravity ends and Spaceship begins gliding decent towards landing. 

## Relays 
- RL1 - Camera Circuit (5V)
- RL2 - Light Circuit (12V)
- RL3 - HAVOC Circuit (19V)
- RL4 - PXIe Circuit (24V)
- RL5? - Batt Circuit (36V)

## ConOps 
- T- 120m: Craft power turns on, craft power circuit recieves power, powers EPD and AdvTech. AdvTech boots, EPD cooling starts, all realys remain open. AdvTech starts code runs whatever self checks it can. 
- T+60m: Spaceship released from launcher vehicle begins boost phase. RL4 is closed powering the PXIe cabinet, PXIe begins boot and interfacing with AdvTech 
- T+61m: 60s after boost begins, RL4 is closed, PXIe cabinet is powered, RL3 is closed powering HAVOC board. Self checks are preformed.
- T+62m: 120s after boost begins, RL1 and RL2 are closed. SLV system is now powered. Cameras begin recording connected to EPD power with a max recording time of 2 hours from memory card limitations. When EPD power is removed (failure or power off) camera batterys can allow the cameras to record for 30 minutes post LOP.
- T+63m: Z-Grav begins, experimental procedure starts. 
- T+63m: Phase configruation 1 is sent to PXIe, config code 1 is sent to signaling device in view of cameras and experiment is preformed. Array configuration 1 is left to execute for ~25s, after which a ~5s settling period begins. 
- T+63.5m: Phase configuration 2 is sent to PXIe, config code 2 is sent to the signaling device. After another total 30 seconds, config 3 is executed.
- T+64: Config 3 
- T+64.5: Config 4 
- T+65: Config 5
- T+65.5: Config 6
- T+66: End of microgravity phase, experimetnal proecude concludes. Power down of all non-essensial electronics. RL3, and RL4 are opened. RL1 and RL2 remain closed to allow for additional observations to be made of fluid during decent.  