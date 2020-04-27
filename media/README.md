## Media Supporting Presentation

<a name="initial_env"/>

### Initial Gazebo Environment
This is the Gazebo environment provided by the ARIAC 2020 Competition. It contains all of the shelves, bins, the gantry robot, some "dummy" parts, and the "real" parts to be picked to fulfill orders.
The "real" parts are in red, green, and blue. 
The initial environment lacks any sensors to determine where the parts have been spawned.  
![Initial Environment - No Sensors](Initial_NoSensors.png)

--- 
<a name="added_sensors"/>

### Gazebo Environment with Sensors
Here I have added 14 logical cameras to the Gazebo environment provided by the ARIAC 2020 Competition. It also contains all of the shelves, bins, the gantry robot, some "dummy" parts, and the "real" parts (in red, green, and blue) to be picked to fulfill orders.
The logical cameras are able to identify the "real" parts in their view by part type and color.
Each logical cameras each has its own reference frame separate from the world frame. The parts detected have their pose and orientation determined with respect to the detecting camera's frame. Thus each part's frame must be transformed with respect to both the world frame and the frame of the end effector that willbe used to pick it up.     
![Sensors - View1](Sensors_View1.png)
![Sensors - View2](Sensors_View2.png)

--- 
<a name="final_version"/>

### Autonomous Order Filling
Here I have added the code to determine where parts have been spawned by reading all of the logical cameras in the scene. 
Each detected part's frame is transformed to the world frame and the end effector frame.
The automated set of orders is read (as a ROS topic; again, provided by the ARIAC competition environment) to determine which parts are needed for each order. 
The location of the next part on the order is parsed to determine how to get the robot to it, and MoveIT is used to calculate the path to the part. 
The robot picks each part and delivers it to the robotic tray assigned to that order.   
```
<a href="http://www.youtube.com/watch?feature=player_embedded&v=V9PfVaut9fU
" target="_blank"><img src="http://img.youtube.com/vi/V9PfVaut9fU/0.jpg" 
alt="Simulation Video" width="640" height="480" border="1" /></a>
```