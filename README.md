# AI-Assisted Botnang Population & Housing WebGIS

This project is an AI-assisted WebGIS for Botnang, Stuttgart. It combines Leaflet WebGIS, PostgreSQL/PostGIS, Docker, and a project-specific AI chatbot called BotnangBot.

## Main Features

- Interactive Leaflet WebGIS map
- Botnang boundary visualization
- Residential building population estimation
- Building type layers
- Population density heatmap
- Scenario and year controls
- BotnangBot connected to PostgreSQL/PostGIS
- Zoom to most populated residential building
- Zoom to least realistic estimated population building
- Zoom to selected building ID

## Technologies Used

- Leaflet.js
- QGIS/qgis2web
- Flask
- PostgreSQL/PostGIS
- Docker
- OpenAI API

## Run Locally with Docker

1. Clone the repository:

```bash
git clone https://github.com/tayebhabib-web/botnang-webgis.git
cd botnang-webgis
