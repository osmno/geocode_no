# geocode2osm

Geocoding for OSM in Norway

## Usage

`python geocode2osm.py [input_file.osm]`

- Will geocode _ADDRESS_ tag in nodes tagged with _GEOCODE=yes_
- Outputs file with _"\_new.osm"_ ending
- Only nodes are supported (not ways and relations)
- Format of ADDRESS: `Skøyen skole, Lørenveien 7, 0585 Oslo` (first part is optional)
- If street address is not found, the program will try to fix common mistakes (vei/veg etc)
- Geocoding results are in three categories:
  - _house_ - exact match with address
  - _street_ - match with street
  - _place_ - closest village/town etc with same name
  - _post district_ - the area given by the post code
- Please edit ADDRESS tags and run the program again to try out corrections
- A detailed log is saved to a _"\_log.txt"_ file
- To geocode a CSV-file, include _latitude_ and _longitude_ columns with 0 (zero) only in the CSV file, load it into JOSM and then save to a OSM file which may be processed by geocode2osm

The following services are used for geocoding:

- [Kartverket cadastral register](https://kartkatalog.geonorge.no/metadata/44eeffdc-6069-4000-a49b-2d6bfc59ac61)
- Kartverket SSR place names
- [Nominatim](https://nominatim.openstreetmap.org/) (limited number of queries)
