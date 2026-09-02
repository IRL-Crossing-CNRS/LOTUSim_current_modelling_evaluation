#include "UnderwaterCurrentPlugin.hh"
#include "GaussMarkovProcess.hh"


using namespace gz;
using namespace sim;
using namespace systems;
using namespace gaussmarkov;
using namespace std::literals::chrono_literals;

UnderwaterCurrentPlugin::UnderwaterCurrentPlugin()
{
  // Doing nothing for now
}


void UnderwaterCurrentPlugin::Configure(const gz::sim::Entity &_entity,
                           const std::shared_ptr<const sdf::Element> &_sdf,
                           gz::sim::EntityComponentManager &_ecm,
                           gz::sim::EventManager &_eventMgr)
{
    ecm_ = &_ecm;

    world_ = _ecm.EntityByComponents(components::World());
    this->worldName = _ecm.Component<gz::sim::components::Name>(world_)->Data();
  gzdbg << "World name : " << this->worldName << std::endl;
  
  if (!_sdf->HasElement("constant_current")) {
    gzerr << "Missing required parameter <current_vel>." << std::endl;
    return;
  }
  
  this->sdfConfig = _sdf->Clone();
 

  sdf::ElementPtr currentVelocityParams = this->sdfConfig->GetElement("constant_current");


  if (currentVelocityParams->HasElement("topic")) {
    this->currentVelocityTopic = currentVelocityParams->Get<std::string>("topic");
    
  }
  else {
  
    this->currentVelocityTopic = "ocean_current";
    
  }

  if (this->sdfConfig->HasElement("csv_output_file")) {
    std::string value = this->sdfConfig->Get<std::string>("csv_output_file");
    std::cout << "Save the simulation in " << value << ".\n" << std::endl;
  } else {
      gzerr << "Missing SDF parameter: csv_output_file" << std::endl;
  }

  

  if (currentVelocityParams->HasElement("velocity")) {
    sdf::ElementPtr elem = currentVelocityParams->GetElement("velocity");
    if (elem->HasElement("mean"))
      this->currentVelModel.mean = elem->Get<double>("mean");
    if (elem->HasElement("min"))
      this->currentVelModel.min = elem->Get<double>("min");
    if (elem->HasElement("max"))
      this->currentVelModel.max = elem->Get<double>("max");
    if (elem->HasElement("mu"))
      this->currentVelModel.mu = elem->Get<double>("mu");
    if (elem->HasElement("noiseAmp"))
      this->currentVelModel.noiseAmp = elem->Get<double>("noiseAmp");
  }


   this->currentVelModel.var = this->currentVelModel.mean;
  gzmsg << "Current velocity [m/s] Gauss-Markov process model:" << std::endl;
  this->currentVelModel.Print();

  if (currentVelocityParams->HasElement("horizontal_angle"))
  {
    sdf::ElementPtr elem =
      currentVelocityParams->GetElement("horizontal_angle");

    if (elem->HasElement("mean"))
      this->currentHorzAngleModel.mean = elem->Get<double>("mean");
    if (elem->HasElement("min"))
      this->currentHorzAngleModel.min = elem->Get<double>("min");
    if (elem->HasElement("max"))
      this->currentHorzAngleModel.max = elem->Get<double>("max");
    if (elem->HasElement("mu"))
      this->currentHorzAngleModel.mu = elem->Get<double>("mu");
    if (elem->HasElement("noiseAmp"))
      this->currentHorzAngleModel.noiseAmp = elem->Get<double>("noiseAmp");
      
   }
   
   this->currentHorzAngleModel.var = this->currentHorzAngleModel.mean;
  gzmsg <<
    "Current velocity horizontal angle [rad] Gauss-Markov process model:"
    << std::endl;
  this->currentHorzAngleModel.Print();

  if (currentVelocityParams->HasElement("vertical_angle"))
  {
    sdf::ElementPtr elem = currentVelocityParams->GetElement("vertical_angle");

    if (elem->HasElement("mean"))
      this->currentVertAngleModel.mean = elem->Get<double>("mean");
    if (elem->HasElement("min"))
      this->currentVertAngleModel.min = elem->Get<double>("min");
    if (elem->HasElement("max"))
      this->currentVertAngleModel.max = elem->Get<double>("max");
    if (elem->HasElement("mu"))
      this->currentVertAngleModel.mu = elem->Get<double>("mu");
    if (elem->HasElement("noiseAmp"))
      this->currentVertAngleModel.noiseAmp = elem->Get<double>("noiseAmp");
  }

  this->currentVertAngleModel.var = this->currentVertAngleModel.mean;
  gzmsg <<
    "Current velocity horizontal angle [rad] Gauss-Markov process model:"
    << std::endl;
  this->currentHorzAngleModel.Print();
   

 

  this->currentVelModel.lastUpdate = 0;
  this->currentHorzAngleModel.lastUpdate = 0;
  this->currentVertAngleModel.lastUpdate = 0;

  this->publisher = this->node.Advertise<msgs::Vector3d>("/ocean_current");
  
  gzmsg << "Current velocity topic name: " << this->ns + "/" + this->currentVelocityTopic << std::endl;
  
  
}


//////////////////////////////////////////////////
void UnderwaterCurrentPlugin::Update(const gz::sim::UpdateInfo &_info,
                                     gz::sim::EntityComponentManager &_ecm)
{
  this->simTime = _info.simTime;

  if (_info.paused) return;

  // Get the total simulation time
  auto totalSimTime = std::chrono::duration_cast<std::chrono::seconds>(_info.simTime).count();

  // Compute simulation time relative
  auto simTimeSec = totalSimTime - this->localSimStartTime;

  // Calculate the flow velocity and the direction using the Gauss-Markov model

  // Update current velocity
  double currentVelMag = this->currentVelModel.Update(simTime.count());

  // Update current horizontal direction around z axis of flow frame
  double horzAngle = this->currentHorzAngleModel.Update(simTime.count());

  // Update current vertical direction around z axis of flow frame
  double vertAngle = this->currentVertAngleModel.Update(simTime.count());

  // Generating the current velocity vector as in the NED frame
  this->currentVelocity = gz::math::Vector3<double>(
      currentVelMag * cos(horzAngle) * cos(vertAngle),
      currentVelMag * sin(horzAngle) * cos(vertAngle),
      currentVelMag * sin(vertAngle));

  // Update time stamp
  this->lastUpdate = simTime;
  this->PublishCurrentVelocity(simTimeSec); // Update logic here

  
  // Define time milestones for saving data (6h, 12h, 18h, 24h)
  std::vector<int> saveTimes = {6 * 3600, 12 * 3600, 18 * 3600, 24 * 3600};

  // Check if we reached a milestone and log the data if not already logged
  for (int saveTime : saveTimes) {
    if (simTimeSec >= saveTime && this->loggedTimes.find(saveTime) == this->loggedTimes.end()) {
      this->loggedTimes.insert(saveTime);  // Mark this time as logged

      std::string csvOutputFile = this->sdfConfig->Get<std::string>("csv_output_file");
      std::ofstream file(csvOutputFile, std::ios::app); // Append mode

      // Check if file is empty to write headers
      bool isEmpty = (file.tellp() == 0);

      if (file.is_open()) {
        if (isEmpty) {
          file << "simTimeSec,CurrentVelocityX,CurrentVelocityY,CurrentVelocityZ\n";
        }

        // Write the data
        file << simTimeSec << ","
              << this->currentVelocity.X() << ","
              << this->currentVelocity.Y() << ","
              << this->currentVelocity.Z() << std::endl;

        file.close();
        std::cout << "Saved velocity data at time: " << saveTime / 3600 << "h.\n";
      }
    }
  }

  gzmsg << "Current velocity mag: " <<  currentVelMag  << std::endl
  << "Horz angle: " <<  horzAngle  << std::endl
  << "Vert angle: " <<  vertAngle  << std::endl;
}



//////////////////////////////////////////////////
void UnderwaterCurrentPlugin::PublishCurrentVelocity(long simTimeSec)
{
  msgs::Vector3d currentVel;
  msgs::Header headerMsg;
  msgs::Set(&currentVel, gz::math::Vector3<double>(this->currentVelocity.X(),
                                           this->currentVelocity.Y(),
                                           this->currentVelocity.Z()));;
                                            
  this->publisher.Publish(currentVel);

  // Add timestamp
  auto stamp = headerMsg.mutable_stamp();
  stamp->set_sec(simTimeSec);

  std::cout << "Publishing velocity at sim time: " << simTimeSec << "s\n";
}

// Register this plugin with the simulator
GZ_ADD_PLUGIN(gaussmarkov::UnderwaterCurrentPlugin,
              gz::sim::System,
              gaussmarkov::UnderwaterCurrentPlugin::ISystemConfigure,
              gaussmarkov::UnderwaterCurrentPlugin::ISystemUpdate)

