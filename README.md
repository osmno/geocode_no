# geocode2osm
Geocoding for OSM in Norway

Usage: <code>python geocode2osm.py [input_file.osm]</code>

* Will geocode *ADDRESS* tag in nodes tagged with *GEOCODE=yes*.
* Outputs file with *"_new.osm"* ending.
* Only nodes are supported (not ways and relations).
* Format of ADDRESS: <code>Skøyen skole, Lørenveien 7, 0585 Oslo</code> (the first part is optional).
* If street address is not found, the program will try to fix common mistakes (vei/veg etc.).
* Geocoding results are provided in three categories:
  * *house* - Exact match with address.
  * *street* - Matches with street.
  * *place* - Closest village/town etc. with same name.
  * *post district* - the area amassed by the postal code.
* Please edit the ADDRESS tags and run the program again to try out corrections.
* A detailed log is saved to a *"_log.txt"* file.
* To geocode a CSV-file, include *latitude* and *longitude* columns with 0 (zero) only in the CSV file, load it into JOSM and then save to a OSM file which may be processed by geocode2osm.

The following services are used for geocoding:
* Kartverket cadastral register.
* Kartverket SSR place names.
* OSM Nominatim (limited number of queries).
