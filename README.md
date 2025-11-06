<div id="top"></div>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]

<br/>

<div align="center">

  <div align="center">
  <h1><code>GLOBAL SEISMIC CATALOG</code></h1>
  </div>

  <p align="center">
    A fully automated and containerized framework for near-real-time integration of global seismic data from heterogeneous open sources.
    <br/>
    <a href="https://github.com/Josemelgahez/global-seismic-catalog/issues">Report a Bug</a>
    ·
    <a href="https://github.com/Josemelgahez/global-seismic-catalog/issues">Request a Feature</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About the Project</a></li>
    <li><a href="#system-architecture">System Architecture</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

---

## About the Project

**Global Seismic Catalog (GSC)** is an open and fully automated framework for the near-real-time integration of global earthquake data from multiple authoritative sources. It provides a reproducible, containerized environment that continuously aggregates and harmonizes seismic events published by **[USGS](https://earthquake.usgs.gov)**, **[EMSC](https://www.seismicportal.eu)**, and **[IGN](https://www.ign.es)**, converting their heterogeneous data structures into a unified and interoperable catalog.

All events are automatically validated, normalized, and enriched with geographic and tectonic context before being stored in a spatially indexed PostgreSQL/PostGIS database. A REST API, implemented with the *Django REST Framework GIS*, exposes the harmonized catalog for direct use in analytical pipelines, visualization platforms, and external monitoring systems.


### Key Features

- Automated acquisition and synchronization of seismic events  
- Cross-source harmonization and validation of metadata  
- Spatial enrichment using tectonic plate and country boundaries  
- Deduplication based on temporal, spatial, and magnitude thresholds  
- REST API for real-time geospatial access  
- Containerized deployment ensuring full reproducibility  
- Automated backups and recovery

<p align="right">(<a href="#top">back to top</a>)</p>

---

## System Architecture

The system is composed of three main containers:

| Service | Description |
|----------|-------------|
| **app** | Django/PostGIS backend managing acquisition, harmonization, and API services |
| **db** | PostgreSQL/PostGIS database storing the unified event catalog |
| **backup** | Automated backup service ensuring database persistence |

![System Architecture](images/architecture.png)

<p align="right">(<a href="#top">back to top</a>)</p>

---

## Getting Started

### Requirements
* **Docker** and **Docker Compose** installed  
* Python 3.12+ (for local testing or extending modules)

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/Josemelgahez/global-seismic-catalog.git
   cd global-seismic-catalog
   ```

2. Build and start the containers
   ```bash
   docker compose up --build
   ```

3. Access the API  
   - **API endpoint:** [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)  
   - **Admin panel:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) 
     > Default credentials: `admin / admin`

<p align="right">(<a href="#top">back to top</a>)</p>

### Backup Service

Database backups are created automatically by the `backup` container and stored in the `/data/backups` directory.  
Each backup is timestamped for traceability and rotated periodically according to the configured retention policy.

By default, a new backup is generated every 24 hours (86,400 seconds), and older backups are automatically deleted once they exceed a retention period of seven days.  
These parameters can be modified through environment variables:
- `BACKUP_INTERVAL_SECONDS` controls how frequently backups are created.
- `BACKUP_RETENTION_DAYS` defines how long each backup is preserved before removal.

---

<p align="right">(<a href="#top">back to top</a>)</p>

## Contact

- Jose Melgarejo Hernández \
✉️ jose.melgarejo@ua.es

- Paula Margarita García-Tapia Mateo \
✉️ paula.garciatapia@ua.es

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/Josemelgahez/global-seismic-catalog?style=for-the-badge
[contributors-url]: https://github.com/Josemelgahez/global-seismic-catalog/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/Josemelgahez/global-seismic-catalog.svg?style=for-the-badge
[forks-url]: https://github.com/Josemelgahez/global-seismic-catalog/network/members
[stars-shield]: https://img.shields.io/github/stars/Josemelgahez/global-seismic-catalog.svg?style=for-the-badge
[stars-url]: https://github.com/Josemelgahez/global-seismic-catalog/stargazers
[issues-shield]: https://img.shields.io/github/issues/Josemelgahez/global-seismic-catalog.svg?style=for-the-badge
[issues-url]: https://github.com/Josemelgahez/global-seismic-catalog/issues
