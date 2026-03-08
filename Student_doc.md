# SYSTEM DESCRIPTION:

<system of the system>

# USER STORIES:

<list of user stories>
1. As a user, I want to click on a sensor widget to open a dedicated detail view showing the current state, metrics, and recent log, so that I can monitor a specific environmental parameter in depth.  

2. As a user, I want to view all sensors' states in a unified dashboard with live updates, so that I can have a complete overview of the Mars habitat environment at a glance.  

3. As a user, I want to be notified when a sensor status is "warning", so that I can react promptly to dangerous conditions.  

4. As a user, I want to view each actuator's current state (ON/OFF) in a dedicated card widget with real-time updates, last change time, and trigger source, so that I always know the actual state of the system.  

5. As a user, I want to view all actuators' states in a unified dashboard where each device has its own card with live status indicators, so that I can monitor and manage the entire system from a single screen.  

6. As a user, I want to toggle an actuator's state by directly interacting with its widget, so that I can manually intervene on the environment without navigating to a separate settings page.  

7. As a user, I want to see the last time an actuator state changed and what triggered the change (manual command or automation rule), so that I can understand recent interventions on the system.  

8. As a user, I want to receive a visual confirmation when I manually toggle an actuator, so that I know my command was received by the system.  

9. As a user, I want to create an automation rule using a simple if-then interface (e.g., if temperature > 30°C → turn on fan), so that I can automate environmental control without writing code.  

10. As a user, I want to edit an existing automation rule, so that I can adapt the system's behaviour as mission parameters change.  

11. As a user, I want to delete an automation rule, so that I can remove obsolete logic and keep the system clean.  

12. As a user, I want to view a list of all automation rules with their current status (active/disabled), so that I can have a clear picture of what logic is running.  

13. As a user, I want to disable an automation rule without deleting it, so that I can temporarily suspend its behaviour and re-enable it later when needed.  

14. As a user, I want to see when an automation rule was last triggered and what action it performed (e.g., "cooling_fan set ON"), so that I can verify if the rule is behaving as intended.  

15. As a user, I want to see the overall system connection status in the top bar, so that I always know if the platform is live or offline.  


# CONTAINERS:

## CONTAINER_NAME: ingestion_services

### DESCRIPTION: 
A Docker container based on Python 3.12-slim that acts as the data ingestion layer of the system. It is designed to run the two core processes: a periodic sensor polling service and a real-time telemetry (SSE) listener. Both processes fetch data from the IoT simulator container, normalize the semi-structured JSON payloads into a flat standard format, and publish the records to RabbitMQ as a server broker.

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>


### PERSISTENCE EVALUATION
The container is completely stateless. No data is persisted locally on the container's file system. All fetched, parsed, and normalized data is immediately forwarded to RabbitMQ

### EXTERNAL SERVICES CONNECTIONS
* External REST API: Connects via HTTP/GET to fetch available sensors and topics, and retrieves data via standard endpoints and SSE streams
* RabbitMQ: Connects to an external AMQP message broker to publish normalized metrics

### MICROSERVICES:

#### MICROSERVICE: sensor_poller
- TYPE: backend
- DESCRIPTION: A synchronous worker process that periodically polls a REST API for sensor data. It fetches the list of available sensors, retrieves their current state, normalizes the nested JSON structures into flat records, and publishes them in batches to the server broker.
- PORTS: None
- TECHNOLOGICAL SPECIFICATION: 
Written in Python 3.12. Uses the requests library for synchronous HTTP GET requests and pika for AMQP communication with RabbitMQ.
- SERVICE ARCHITECTURE: 
Operates on a continuous polling loop with a configurable sleep interval (default 10 seconds). In each cycle, it queries the API for active sensor IDs, fetches data for each ID sequentially, aggregates the responses, normalizes them, and publishes

#### MICROSERVICE: telemetry_listener
- TYPE: backend
- DESCRIPTION: An asynchronous worker process that maintains long-lived Server-Sent Events (SSE) connections to stream real-time telemetry data. It listens to multiple topics simultaneously, normalizes incoming events on the fly, and publishes them to the message broker.
- PORTS: None
- TECHNOLOGICAL SPECIFICATION: 
Written in Python 3.12. Uses requests with stream=True to parse SSE chunks and pika for RabbitMQ. Utilizes the built-in threading module for concurrency.
- SERVICE ARCHITECTURE: 
Multi-threaded architecture. Upon startup, it fetches the list of available telemetry topics from the API. It then spawns a dedicated daemon thread for each topic. To guarantee thread safety with the pika library, each thread utilizes a factory function to instantiate and manage its own independent connection to RabbitMQ. The threads handle automatic reconnection with a backoff delay in case the SSE stream drops or times out.

#### <other microservices>


## CONTAINER_NAME: automation-engine

### DESCRIPTION: 
<description of the container>

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>

### DESCRIPTION:
<description of the container>

### PERSISTENCE EVALUATION
<description on the persistence of data>

### EXTERNAL SERVICES CONNECTIONS
<description on the connections to external services>

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>

## <other containers>
<-------------------->
## CONTAINER_NAME: frontend-module

### DESCRIPTION: 
<description of the container>

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>

### DESCRIPTION:
<description of the container>

### PERSISTENCE EVALUATION
<description on the persistence of data>

### EXTERNAL SERVICES CONNECTIONS
<description on the connections to external services>

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>


<-------------->
## CONTAINER_NAME: postgres

### DESCRIPTION: 
<description of the container>

### USER STORIES:
<list of user stories satisfied>

### PORTS: 
<used ports>

### DESCRIPTION:
<description of the container>

### PERSISTENCE EVALUATION
<description on the persistence of data>

### EXTERNAL SERVICES CONNECTIONS
<description on the connections to external services>

### MICROSERVICES:

#### MICROSERVICE: <name of the microservice>
- TYPE: backend
- DESCRIPTION: <description of the microservice>
- PORTS: <ports to be published by the microservice>
- TECHNOLOGICAL SPECIFICATION:
<description of the technological aspect of the microservice>
- SERVICE ARCHITECTURE: 
<description of the architecture of the microservice>

- ENDPOINTS: <put this bullet point only in the case of backend and fill the following table>
		
	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
    | ... | ... | ... | ... |

- PAGES: <put this bullet point only in the case of frontend and fill the following table>

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| ... | ... | ... | ... |

- DB STRUCTURE: <put this bullet point only in the case a DB is used in the microservice and specify the structure of the tables and columns>

	**_<name of the table>_** :	| **_id_** | <other columns>

#### <other microservices>