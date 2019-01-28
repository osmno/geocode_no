#!/usr/bin/env python
# -*- coding: utf8

# geocode2osm
# Geocodes nodes in OSM xml file marked with GEOCODE=yes and ADDRESS=* using a variety of techniques
# Usage: python geocode_osm.py [input_filename.osm]
# Geocoded file will be written to input_filename + "_new.osm"
# Log is written to "geocode_log.txt"


import json
import sys
import urllib
import urllib2
import csv
import time
import re
import copy
from xml.etree import ElementTree


version = "0.1.1"

header = {"User-Agent": "osm-no/geocode2osm/" + version}


# Translation table for other information than street names

fix_name = [
	(u"Rådhuset", u"Rådhus"),
	("Kommunehuset", "Kommunehus"),
	("Herredshuset", "Herredshus"),
	("Heradshuset", "Heradshus"),
	("st.", "stasjon"),
	("sk.", "skole"),
	("vgs.", u"videregående skole"),
	("v.g.s.", u"videregående skole"),
	("b&u", "barne og ungdom")
	]


# Translation table for street name corrections
# Code will also test i) without ".", ii) with preceding "s" and iii) will test combinations with synonyms

street_synonyms = [
	['gata', 'gaten', 'gate', 'gt.', 'g.'],
	['veien', 'vegen', 'vei', 'veg', 'vn.', 'v.'],
	['plassen', 'plass', 'pl.'],
	['torv', 'torg'],
	['bro', 'bru'],
	['brygga', 'bryggen', 'brygge', 'br.'],
	['gamle', 'gml.'],
	['kirke', 'kyrkje', 'krk.'],
	['skole', 'skule', 'sk.']
	]

# This table is not yet supported in the code:

extra_synonyms = [
	['kirke', 'kyrkje'],
	['skole', 'skule'],
	[u'videregående skole', u'videregåande skule'],
	[u'rådhus', u'rådhuset'],
	['kommunehus', 'kommunehuset'],
	['herredshus', 'herredshuset', 'heradshus', 'heradshuset'],
	['krk.', 'kirke'],
	['st.', 'stasjon'],
	['v.g.s.', u'videregående skole']
	]


# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()


# Log query results

def log(log_text):

	log_file.write(log_text.encode("utf-8"))


# Open file/api, try up to 5 times, each time with double sleep time

def try_urlopen (url):

	tries = 0
	while tries < 5:
		try:
			return urllib2.urlopen(url)
		except urllib2.HTTPError, e:
			if e.code in [429, 503, 504]:  # Too many requests, Service unavailable or Gateway timed out
				if tries  == 0:
					message ("\n") 
				message ("\r\tRetry %i in %ss... " % (tries + 1, 5 * (2**tries)))
				time.sleep(5 * (2**tries))
				tries += 1
			else:
				message ("\n\nHTTP error %i: %s\n" % (e.code, e.reason))
				sys.exit()
	
	message ("\n\nHTTP error %i: %s\n" % (e.code, e.reason))
	sys.exit()


# Concatenate address line

def get_address(street, house_number, postal_code, city):

	address = street
	if house_number:
		address = address + " " + house_number  # Includes letter
	if address:
		address = address + ", "
	if postal_code:
		address = address + postal_code + " "
	if city:
		address = address + city

	return address.strip()


# Geocoding with Nominatim

def nominatim_search (query_type, query_text, query_municipality, method):

	global nominatim_count, bbox, last_nominatim_time

	# Allow 1 second delay
	time_now = time.time()
	if time_now < last_nominatim_time + 1:
		time.sleep(1 - time_now + last_nominatim_time)

	if not(bbox):
		bbox = get_municipality_data(query_municipality)

	url = "https://nominatim.openstreetmap.org/search?%s=%s&countrycodes=no&viewbox=%f,%f,%f,%f&format=json&limit=10" \
							% (query_type, urllib.quote(query_text.encode('utf-8')),
								bbox['longitude_min'], bbox['latitude_min'], bbox['longitude_max'], bbox['latitude_max'])

	request = urllib2.Request(url, headers=header)
	file = try_urlopen(request)
	result = json.load(file)
	file.close()

	log ("Nominatim (%s): %s=%s\n" % (method, query_type, query_text))
	log (json.dumps(result, indent=2))
	log ("\n")
	nominatim_count += 1
	last_nominatim_time = time.time()

	if result:
		if (result[0]['class'] != "boundary") or (result[0]['type'] != "administrative"):  # Skip administrative boundaries (municipalities)
			result = result[0]
		elif len(result) > 1:
			result = result[1]
		else:
			return None

		# Check if coordinates are within the bounding box of the municipality

		latitude = float(result['lat'])
		longitude = float(result['lon'])

		if (latitude > bbox['latitude_min']) and (latitude < bbox['latitude_max']) and \
			(longitude > bbox['longitude_min']) and (longitude < bbox['longitude_max']):
			result_type = "Nominatim/%s -> %s/%s" % (method, result['class'], result['type'])
			if result['class'] == "highway":
				result_quality = "street"
			elif method.find("address") >= 0:
				result_quality = "place"
			else:
				result_quality = "post district"
			return (result['lat'], result['lon'], result_type, result_quality)
		else:
			log ("Nominatim result not within bounding box of municipality\n")
			return None

	else:
		return None


# Geocoding with Matrikkel Vegadresse

def matrikkel_search (street, house_number, house_letter, post_code, city, method):

	global matrikkel_count

	query = ""
	if street:
		query += "sok=%s" % urllib.quote(street.encode('utf-8'))
	if house_number:
		query += "&nummer=%s" % house_number
	if house_letter:
		query += "&bokstav=%s" % house_letter
	if post_code:
		query += "&postnummer=%s" % post_code
	if city:
		query += "&poststed=%s" % urllib.quote(city.encode('utf-8'))

	url = "https://ws.geonorge.no/adresser/v1/sok?" + query + "&treffPerSide=10"

	request = urllib2.Request(url, headers=header)
	file = try_urlopen(request)
	result = json.load(file)
	file.close()

	result = result['adresser']

	log ("Matrikkel (%s): %s\n" % (method, urllib.unquote(query)))
	log (json.dumps(result, indent=2))
	log ("\n")
	matrikkel_count += 1

	if result:
		result_type = "Matrikkel/%s -> %s" % (method, result[0]['objtype'])
		latitude = result[0]['representasjonspunkt']['lat']
		longitude = result[0]['representasjonspunkt']['lon']
		if method.find("address") >= 0:
			result_quality = "house"
		else:
			result_qutlity = "place"
		return (str(latitude), str(longitude), result_type, result_quality)
	else:
		return None


# Geocoding with SSR

def ssr_search (query_text, query_municipality, method):

	global ssr_count, ssr_not_found

	query = "https://ws.geonorge.no/SKWS3Index/ssr/json/sok?navn=%s&epsgKode=4326&fylkeKommuneListe=%s&eksakteForst=true" \
				% (urllib.quote(query_text.encode('utf-8')), query_municipality)
	request = urllib2.Request(query, headers=header)
	file = try_urlopen(request)
	result = json.load(file)
	file.close()

	log ("SSR (%s): %s, %s municipality\n" % (method, query_text, query_municipality))
	log (json.dumps(result, indent=2))
	log ("\n")
	ssr_count += 1

	if "stedsnavn" in result:
		if isinstance(result['stedsnavn'], dict):
			result['stedsnavn'] = [ result['stedsnavn'] ]

		# Check if name type is defined in category table
		for place in result['stedsnavn']:
			if not(place['navnetype'].lower().strip() in ssr_types):
				message ("\n\t**** SSR name type '%s' not found - please post issue at 'https://github.com/osmno/geocode2osm' ****\n\n"\
							% (place['navnetype'], ssr_filename))
				log ("SSR name type '%s' not found\n" % place['navnetype'])
				if not(place['navnetype'] in ssr_not_found):
					ssr_not_found.append(place['navnetype'])

		for place in result['stedsnavn']:
			if (place['navnetype'].lower().strip() in ssr_types) and \
					(ssr_types[ place['navnetype'].lower().strip() ] in ['Bebyggelse', 'OffentligAdministrasjon', 'Kultur']):
				result_type = "SSR/%s -> %s" % (method, place['navnetype'].strip())
				if method == "street":
					result_quality = "place"
				else:
					result_quality = "post district"
				return (place['nord'], place['aust'], result_type, result_quality)
	
	return None


# Load bounding box for given municipality ref

def get_municipality_data (query_municipality):

	bbox = {
		'latitude_min': 90.0,
		'latitude_max': -90.0,
		'longitude_min': 180.0,
		'longitude_max': -180.0
		}

	if query_municipality and (query_municipality != "2100"):  # Exclude Svalbard
		query = "https://ws.geonorge.no/kommuneinfo/v1/kommuner/%s" % query_municipality
		request = urllib2.Request(query, headers=header)
		file = try_urlopen(request)
		result = json.load(file)
		file.close()

		for node in result['avgrensningsboks']['coordinates'][0][1:]:
			bbox['latitude_max'] = max(bbox['latitude_max'], node[1])
			bbox['latitude_min'] = min(bbox['latitude_min'], node[1])
			bbox['longitude_max'] = max(bbox['longitude_max'], node[0])
			bbox['longitude_min'] = min(bbox['longitude_min'], node[0])

	log ("Bounding box for municipality #%s: (%f, %f) (%f, %f)\n" % \
			(query_municipality, bbox['latitude_min'], bbox['longitude_min'], bbox['latitude_max'], bbox['longitude_max']))

	return bbox

# Look up synonyms

def try_synonyms (street, house_number, house_letter, postcode, city):

	low_street = street.lower() + " "

	for synonyms in street_synonyms:
		found = False

		for synonym_word in synonyms:

			if "." in synonym_word:
				test_list = [synonym_word, synonym_word[:-1]]  # Abreviation with and without period
			else:
				test_list = [synonym_word]

			for test_word in test_list:

				# Test synonyms

				if low_street.find(test_word + " ") >= 0:
					found = True
					for synonym_replacement in synonyms:
						if (synonym_replacement != synonym_word) and not("." in synonym_replacement):

							new_street = low_street.replace(test_word, synonym_replacement)
							result = matrikkel_search (new_street, house_number, house_letter, postcode, city, "address+synonymfix")
							if (result):
								return result

				# Test space after genitive "s", then also with synonyms

				if low_street.find("s" + test_word + " ") >= 0:

					new_street = low_street.replace("s" + test_word, "s " + test_word)
					result = matrikkel_search (new_street, house_number, house_letter, postcode, city, "address+genitivefix")
					if (result):
						return result

					for synonym_replacement in synonyms:
						if (synonym_replacement != synonym_word) and not("." in synonym_replacement):
							new_street = low_street.replace("s" + test_word, "s " + synonym_replacement)
							result = matrikkel_search (new_street, house_number, house_letter, postcode, city, "address+allfix")
							if (result):
								return result

			if found:
				break  # Already match in synonym group, so no need to test rest of the group

	return None


# Main program

if __name__ == '__main__':

	# Read all data into memory

	message ("\nLoading data...")
	
	if len(sys.argv) > 1:
		filename = sys.argv[1]
	else:
		message ("Please include input osm filename as parameter\n")
		sys.exit()

#	parser = ElementTree.XMLParser(encoding="utf-8")
#	tree = ElementTree.parse(filename, parser=parser)
	tree = ElementTree.parse(filename)

	# Load post code districts from Posten

	post_filename = 'https://www.bring.no/postnummerregister-ansi.txt'
	file = urllib2.urlopen(post_filename)
	postal_codes = csv.DictReader(file, fieldnames=['post_code','post_city','municipality_ref','municipality_name','post_type'], delimiter="\t")
	post_districts = {}

	for row in postal_codes:
		entry = {
			'city': row['post_city'].decode("windows-1252"),
			'municipality_ref': row['municipality_ref'],
			'municipality_name': row['municipality_name'].decode("windows-1252"),
			'type': row['post_type'],  # G, P or B
			'multiple': False
		}

		# Discovre possible multiples post code districts for the same city name
		if entry['type'] == "G":
			for post_code, post in post_districts.iteritems():
				if (post['city'] == entry['city']) and (post['type'] == "G"):
					post['multiple'] = True
					entry['multiple'] = True

		post_districts[row['post_code']] = entry

	# Load name categories from Github

	ssr_filename = 'https://raw.githubusercontent.com/osmno/geocode2osm/master/navnetyper.json'
	file = urllib2.urlopen(ssr_filename)
	name_codes = json.load(file)
	file.close()

	ssr_types = {}
	for main_group in name_codes['navnetypeHovedgrupper']:
		for group in main_group['navnetypeGrupper']:
			for name_type in group['navnetyper']:
				ssr_types[ name_type['visningsnavn'].strip().lower() ] = main_group['navn']

	# Init output files

	message ("\nGeocoding objects marked with GEOCODE key in file '%s'...\n\n" % filename)

	log_filename = "geocode_log.txt"
	log_file = open(log_filename, "w")

#	result_file = open("geocode_result.osm", "w")
#	result_file.write ('<?xml version="1.0" encoding="UTF-8"?>\n')
#	result_file.write ('<osm version="0.6" generator="geocode_osm v%s" upload="false">\n' % version)

	nominatim_count = 0
	ssr_count = 0
	matrikkel_count = 0
	tried_count = 0
	geocode_count = 0
	ssr_not_found = []
	last_nominatim_time = time.time()

	hits = {
		'house': 0,
		'street': 0,
		'place': 0,
		'post district': 0
	}

	root = tree.getroot()

	# Loop through all elements

	for node in root.iter('node'):

		address_tag = node.find("tag[@k='ADDRESS']")
		geocode_tag = node.find("tag[@k='GEOCODE']")

		if (geocode_tag != None) and (address_tag != None) and (geocode_tag.get("v").lower() != "no"):

			# Format address for better match in Nominatim

			tried_count += 1
			address = address_tag.get("v")
			message ("%i %s " % (tried_count, address))

			address_split = address.split(",")
			length = len(address_split)
			for i in range(length):
				address_split[i] = address_split[i].strip()

			if length > 1:
				street = address_split[length - 2]
				postcode = address_split[length - 1][0:4]
				city = address_split[length - 1][5:].strip()
				house_number = ""
				house_letter = ""

				reg = re.search(r'(.*) [0-9]+[ \-\/]+([0-9]+)[ ]*([A-Za-z]?)$', street)
				if not(reg):
					reg = re.search(r'(.*) ([0-9]+)[ ]*([A-Za-z]?)$', street)				
				if reg:
					street = reg.group(1).strip()
					house_number = reg.group(2).upper()
					house_letter = reg.group(3)

				if length > 2:
					street_extra = ", ".join(address_split[0:length - 2])
				else:
					street_extra = ""

				# Better match in Nominatim
				for swap in fix_name:
					street = street.replace(swap[0], swap[1] + " ").replace("  "," ").strip()
					street_extra = street_extra.replace(swap[0], swap[1] + " ").replace("  "," ").strip()

			else:
				street = ""
				street_extra = ""
				house_number = ""
				house_letter = ""
				postcode = address[0:4]
				city = address[5:].strip()

			if postcode in post_districts:
				municipality_ref = post_districts[postcode]['municipality_ref']
				municipality_name = post_districts[postcode]['municipality_name']
				postcode_name = post_districts[postcode]['city']
			else:
				municipality_ref = ""
				municipality_name = ""
				postcode_name = ""

			bbox = None

			# Attempt to geocode address

			log ("\nADDRESS: %s\n" % address)
			log ("[%s], [%s] [%s][%s], [%s] [%s (%s)]\n" % (street_extra, street, house_number, house_letter, postcode, city, postcode_name))
			log ("Municipality #%s: %s\n" % (municipality_ref, municipality_name))

			result = None

			# First try to find exact location

			if street:

				if house_number:
					result = matrikkel_search (street, house_number, house_letter, postcode, city, "address")

					if not(result):
						result = matrikkel_search (street, house_number, house_letter, postcode, "", "address+postcode")

					if not(result):
						result = matrikkel_search (street, house_number, house_letter, "", city, "address+city")

					if not(result):
						result = try_synonyms (street, house_number, house_letter, postcode, city)

				if not(result) and not(house_number) and municipality_ref:
					result = ssr_search (street, municipality_ref, "street")

				if not(result) and street_extra:
					result = nominatim_search ("q", get_address(street_extra + ", " + street, house_number, postcode, ""),\
								municipality_ref, "address+extra")

				if not(result):
					result = nominatim_search ("q", get_address(street, house_number, postcode, ""), municipality_ref, "address")

				if not(result) and not(house_number):
					result = matrikkel_search (street, "", "", postcode, city, "street")

					if not(result) and postcode_name and (postcode_name != city.upper()):
						result = matrikkel_search (street, "", "", postcode, "", "street+postcode")

			# Try to find village of post district if only one district per city

			if not(result) and city and municipality_ref:

				# Find city location if city has only one post district
				if post_districts[postcode]['multiple'] == False:
					result = ssr_search (city, municipality_ref, "city")

					if not(result) and (postcode_name != city.upper()):
						result = ssr_search (postcode_name, municipality_ref, "postname")

					if not(result):
						result = nominatim_search ("q", get_address (city, "", postcode, ""), municipality_ref, "city")

			# Try to find polygon center of post district

			if not(result) and postcode:
				result = nominatim_search ("postalcode", postcode, municipality_ref, "postcode")

			# Try to find village center of city

			if not(result) and city and municipality_ref:
				result = ssr_search (city, municipality_ref, "city")

				if not(result) and (postcode_name != city.upper()):
					result = ssr_search (postcode_name, municipality_ref, "postname")

#			if not(result) and city:
#				result = matrikkel_search ("", "", "", "", city, "city")  # Arbitrary address??

#				if not(result) and postcode_name and (postcode_name != city.upper()):
#					result = matrikkel_search ("", "", "", "", postcode_name, "postname")

			if not(result) and postcode_name:

				if municipality_name != city.upper():
					result = nominatim_search ("q", get_address (postcode_name, "", "", postcode_name), municipality_ref, "city")

				if not(result):
					result = nominatim_search ("city", postcode_name, municipality_ref, "city")

			# If successful, update coordinates and save geocoding details for information

			if result:

				latitude = result[0]
				longitude = result[1]
				result_type = result[2]
				result_quality = result[3]

				node.set("lat", latitude)
				node.set("lon", longitude)
				node.set("action", "modify")

				tag = node.find("tag[@k='GEOCODE_METHOD']")
				if tag != None:
					tag.set("v", result_type)
				else:
					node.append(ElementTree.Element("tag", k="GEOCODE_METHOD", v=result_type))

				tag = node.find("tag[@k='GEOCODE_RESULT']")
				if tag != None:
					tag.set("v", result_quality)
				else:
					node.append(ElementTree.Element("tag", k="GEOCODE_RESULT", v=result_quality))

				message ("--> %s (%s)\n" % (result_type, result_quality))
				log ("MATCH WITH %s (precision: %s)\n" % (result_type, result_quality))
#				result_file.write(ElementTree.tostring(node))
				geocode_count += 1

				hits[result_quality] += 1

			else:
				message ("--> NO MATCH\n")
				log ("NO MATCH\n")

				tag = node.find("tag[@k='GEOCODE_RESULT']")
				if tag != None:
					tag.set("v", "no match")
				else:	
					node.append(ElementTree.Element("tag", k="GEOCODE_RESULT", v="not found"))

				tag = node.find("tag[@k='GEOCODE_METHOD']")
				if tag != None:
					node.remove(tag)

#				result_file.write(ElementTree.tostring(node))

	# Wrap up

	if filename.find(".osm") >= 0:
		filename = filename.replace(".osm", "_new.osm")
	else:
		filename = filename + "_new.osm"

	tree.write(filename, encoding='utf-8', method='xml', xml_declaration=True)

#	result_file.write('</osm>')
#	result_file.close()

	log ("\nNominatim: %i\n" % nominatim_count)
	log ("Matrikkel: %i\n" % matrikkel_count)
	log ("SSR:       %i\n" % ssr_count)

	message ("\nGeocoded %i of %i objects, written to file '%s'\n" % (geocode_count, tried_count, filename))
	message ("Hits: %i houses (exact addresses), %i streets, %i places (villages, towns), %i post code districts\n" % \
				(hits['house'], hits['street'], hits['place'], hits['post district']))
	message ("Nominatim queries: %i (max approx. 600/hour)\n" % nominatim_count)
	message ("Detailed log in file '%s'\n\n" % log_filename)

	if ssr_not_found:
		message ("SSR name types not found: %s - please post issue at 'https://github.com/osmno/geocode2osm'\n" % str(ssr_not_found))

	log_file.close()
  
