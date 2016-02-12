from pykml.factory import KML_ElementMaker as KML
from pykml.factory import GX_ElementMaker as GX
from pykml.parser import Schema
import pandas as pd
from datetime import datetime
from lxml import etree
from math import radians, cos, sin, asin, sqrt, pi, atan2
from googleplaces import GooglePlaces, types, lang
 
google_places = GooglePlaces("You wish")

previousPoint = None
pLat = None
pLong = None
pTime = None

timeStopped = 0
notableStopLength = 30
rowStopped = None
allStops = []
hasStopped = False

lineReduceNumBy = 15
count = 0

topSpeed = 3.8;
minSpeed = 0;

def getDistanceFromLatLonInKm(lat1,lon1,lat2,lon2):
	R = 6371; # Radius of the earth in km
	dLat = deg2rad(lat2-lat1)  # deg2rad below
	dLon = deg2rad(lon2-lon1) 
	a = sin(dLat/2) * sin(dLat/2) + cos(deg2rad(lat1)) * cos(deg2rad(lat2)) * sin(dLon/2) * sin(dLon/2)

	c = 2 * atan2(sqrt(a), sqrt(1-a)); 
	d = R * c # Distance in km
	return d
	

def deg2rad(deg):
	return deg * (pi/180)

def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

class AStop:
	def __init__(self, startTime, lat, lng, timeStart):
		self.lat = lat
		self.long = lng
		self.timeStart = timeStart
		self.timeEnd = startTime
		self.time = self.timeEnd - self.timeStart
		self.marked = False
		self.ignore = False

	def __eq__(self, other):
		return self.lat == other.lat and self.long == other.long

# read data
df = pd.read_csv("pubData.csv")

# prepare kml
_doc = KML.kml()
doc = etree.SubElement(_doc, 'Document')

doc.append(
	KML.Style(
		KML.LineStyle(
			KML.color('ffff0000'),
			KML.width(4)
			),
		id = "slowest"
		)
	)
doc.append(
	KML.Style(
		KML.LineStyle(
			KML.color('ffcc00cc'),
			KML.width(4)
			),
		id = "slow"
		)
	)
doc.append(
	KML.Style(
		KML.LineStyle(
			KML.color('5014F0FF'),
			KML.width(4)
			),
		id = "medium"
		)
	)
doc.append(
	KML.Style(
		KML.LineStyle(
			KML.color('501478FF'),
			KML.width(4)
			),
		id = "fast"
		)
	)
doc.append(
	KML.Style(
		KML.LineStyle(
			KML.color('ff0000ff'),
			KML.width(4)
			),
		id = "fastest"
		)
	)

def append_linestring(timeDiff, dist, normalized, thisStyle, row):
	doc.append(
		KML.Placemark(
			KML.name("Point " + str(count/lineReduceNumBy)),
			KML.ExtendedData(
				KML.Data(KML.value(timeDiff), name="Time Length"),
				KML.Data(KML.value(dist), name="Distance Metres"),
				KML.Data(KML.value(dist/timeDiff.seconds), name="Average Speed m/s"),
				KML.Data(KML.value(normalized), name="Normalized Speed"),
			),
			KML.styleUrl("#{}".format(thisStyle)),
			KML.LineString(
				KML.extrude('1'),
				GX.altitudeMode('relative'),
				KML.coordinates(
					previousPoint,
					"{},{},{}".format(row['LOCATION Longitude : '],row['LOCATION Latitude : '],0)
				)						
			)

		))

#loop through csv data
for i, row, in df.iterrows():

	# We have loads of data, so only use 1 in X rows to avoid spamming the map
	if count%lineReduceNumBy == 0:

		thisTime = datetime.strptime(row['YYYY-MO-DD HH-MI-SS_SSS'], "%Y-%m-%d %H:%M:%S:%f")
		

		# If this isn't the first point we're examining...
		if previousPoint != None:
			timeDiff = thisTime - pTime
			
			# ... get the kilometre distance from the previous point and use that + time diff to get average speed
			dist = getDistanceFromLatLonInKm(pLong, pLat, row['LOCATION Longitude : '],row['LOCATION Latitude : ']) * 1000

			# Normalize the speed between 0->1 for easy categorizations
			normalized = (dist/timeDiff.seconds -minSpeed)/(topSpeed-minSpeed)

			if normalized > 1:
				normalized = 1;

			# Assign a colour style based on average speed
			thisStyle = "slowest"
			if normalized >= 0.8:
				thisStyle = "fastest"
			elif normalized >= 0.6:
				thisStyle = "fast"
			elif normalized >= 0.4:
				thisStyle = "medium"
			elif normalized > 0.2:
				thisStyle = "slow"

			# If moving super slow...
			if normalized < 0.15:

				# ...add onto continous time spent stopped ...
				timeStopped += timeDiff.seconds

				#... and if this is the first stop after movement, save this row's details
				if not hasStopped:
					print "New stop!"
					hasStopped = True
					rowStopped = row

				print "Very slow for {} seconds".format(timeStopped)

			# If we've moved after being stopped, save it for checking later
			elif timeStopped > 0:

				allStops.append(AStop(thisTime, 
					rowStopped['LOCATION Latitude : '], 
					rowStopped['LOCATION Longitude : '], 
					datetime.strptime(rowStopped['YYYY-MO-DD HH-MI-SS_SSS'], "%Y-%m-%d %H:%M:%S:%f")))

				timeStopped = 0
				hasStopped = False
				append_linestring(timeDiff, dist, normalized, thisStyle, row)

			# if we're moving and have been moving, just make a line between this and the last point
			else:
				append_linestring(timeDiff, dist, normalized, thisStyle, row)

		# Save this point's details in memory for the next row to compare to
		previousPoint = "{},{},{}".format(row['LOCATION Longitude : '],row['LOCATION Latitude : '],row['LOCATION Altitude ( m)'])
		pLat = row['LOCATION Latitude : ']
		pLong = row['LOCATION Longitude : ']
		pTime = thisTime  

	count += 1

if timeStopped > 0:
	allStops.append(AStop(thisTime, 
					rowStopped['LOCATION Latitude : '], 
					rowStopped['LOCATION Longitude : '], 
					datetime.strptime(rowStopped['YYYY-MO-DD HH-MI-SS_SSS'], "%Y-%m-%d %H:%M:%S:%f")))

stopsToAdd = []

# Merge stops which are close together (could be caused by dodgy GPS signals)
# Loop over all stops, adding them to the add list if they're long enough
# Compare any already looped over stops, merging their times if they're close
for i, st in enumerate(allStops):

	if i > 0:
		j = i - 1
		while j >= 0:

			if allStops[j].ignore:
				j -= 1
				continue

			met = getDistanceFromLatLonInKm(allStops[j].lat, allStops[j].long, allStops[i].lat, allStops[i].long) * 1000
			if met > 50:
				j -= 1
				continue

			timeDiff = abs(st.timeStart - allStops[j].timeEnd)
			if timeDiff.seconds > 150:
				j -= 1
				continue

			if allStops[j].marked:
				ind = stopsToAdd.index(allStops[j])
				stopsToAdd[ind].time += st.time
				st.ignore = True
				break
			else:
				st.time += allStops[j].time

			j -= 1
			

	if not st.ignore and st.time.seconds >= notableStopLength:
		st.marked = True
		stopsToAdd.append(st)

# We've got the final list of stops, add them to the KML
# Check to see if we can get the bar information from google places API
for ind, stop in enumerate(stopsToAdd):

	query_result = google_places.nearby_search(
		lat_lng={'lat': stop.lat, 'lng': stop.long}, radius=40, types=[types.TYPE_BAR])

	placename = "Unknown place"
	placephoto = "https://d30y9cdsu7xlg0.cloudfront.net/png/250091-200.png"
	
	if query_result.places:

		thisPlace = query_result.places[0]
		thisPlace.get_details()
		placename = thisPlace.name
		if thisPlace.photos:
			thisPlace.photos[0].get(maxheight=500, maxwidth=500)
			placephoto = thisPlace.photos[0].url
		print "Found {} at {}".format(placename, query_result.places[0].geo_location)

	description = '<img src="{}" />'.format(placephoto)

	if ind > 0:
		description = description + "Hey, it looks like you're at {} on a pub crawl. Want to see other bars in your area?".format(placename)

	doc.append(
		KML.Placemark(
			KML.name("Stopped at: {}".format(placename)),
			KML.description(description),
			KML.ExtendedData(
				KML.Data(KML.value(stop.time.seconds), name="Time Length")
			),
			KML.Point(
				KML.coordinates(
					"{},{}".format(stop.long, stop.lat)
				)
			)	
		))

# output a KML file
outfile = file('kmloutput.kml','w')
outfile.write(etree.tostring(doc, pretty_print=True))