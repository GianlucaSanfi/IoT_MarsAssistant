# SYSTEM DESCRIPTION:

<system of the system>

# USER STORIES:

<list of user stories>


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


## CONTAINER_NAME: <name of the container>

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