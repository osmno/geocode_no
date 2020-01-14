# geocode2osm
Geocoding for OSM in Norway.

Usage: <code>python geocode2osm.py [input_file.osm]</code>.

* Geocodes the *ADDRESS* tag in nodes tagged with *GEOCODE=yes*.
* Outputs a file with *"_new.osm"* ending.
* Only nodes are supported (not ways and relations).
* Format of ADDRESS: <code>Skøyen skole, Lørenveien 7, 0585 Oslo</code> (the first part is optional).
* If street address is not found, the program tries to fix common mistakes (vei/veg etc.).
* Geocoding results are in divided into three categories:
  * *House* - exact match with address.
  * *Street* - matchs with street.
  * *Place* - closest village/town etc. sharing the same name.
  * *Post district* - the area given by post code.
* Please edit ADDRESS tags and run the program again to try out corrections.
* A detailed log is saved to a *"_log.txt"* file.
* To geocode a CSV-file, include *latitude* and *longitude* columns with only 0 (zero) in the CSV file, load it into JOSM and then save to a OSM file which may be processed by geocode2osm.

The following services are used for geocoding:
* Kartverket cadastral register.
* Kartverket SSR place names.
* OSM Nominatim (limited number of queries).
