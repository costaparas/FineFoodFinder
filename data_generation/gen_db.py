#!/usr/bin/python
#Written by Costa Paraskevopoulos in April 2017
#Generates a mock database for the Fine Food Finder

#Requires the following to be present in the current directory:
#names.txt - http://listofrandomnames.com/
#emails.txt - https://www.randomlists.com/email-addresses
#suburbs.txt - Andrew Taylor
#restaurants - generated by scrape_zomato.pl

import sqlite3, sys, random, os, re, glob, urllib
from HTMLParser import HTMLParser

def main():
	db = sqlite3.connect("../data.db")
	db.text_factory = str
	c = db.cursor()
	c.execute("PRAGMA foreign_keys = ON")

	#generate and populate database tables
	tables = ['Ratings', 'Restaurants', 'Users', 'Reviews']
	drop_tables(c, tables)
	create_tables(c)
	populate_tables(c)

	db.commit()
	db.close()

#drops all old tables if they exist
def drop_tables(c, tables):
	for table in tables:
		print 'Dropping %s table...' %table
		try:
			c.execute('DROP TABLE ' + table)
		except sqlite3.OperationalError:
			pass

#creates fresh tables
def create_tables(c):

	print 'Creating Users table...'
	c.execute(
		'''CREATE TABLE Users (
				full_name	TEXT not null,
				username		TEXT not null unique,
				password		TEXT not null,
				email			TEXT not null unique check (email like '_%@_%'),
				status      TEXT not null,
				PRIMARY KEY (username)
			);''')

	print 'Creating Restaurants table...'
	c.execute(
		'''CREATE TABLE Restaurants (
				id			INTEGER not null unique,
				name		TEXT not null,
				suburb	TEXT not null,
				address	TEXT not null,
				postcode INTEGER not null,
				phone		TEXT,
				hours		TEXT, -- business hours; varying format
				cuisine	TEXT not null,
				owner		TEXT,
				website	TEXT check (website like 'http%://%'),
				cost		FLOAT, -- average cost per person
				image		TEXT check (image like 'http%://%'),
				PRIMARY KEY (id),
				FOREIGN KEY (owner) REFERENCES Users(username)
			);''')

	print 'Creating Ratings table...'
	c.execute(
		'''CREATE TABLE Ratings (
				user		TEXT not null,
				restaurant	INTEGER not null,
				rating		FLOAT not null,
				PRIMARY KEY (user, restaurant), -- one rating per user per restaurant
				FOREIGN KEY (user) REFERENCES Users(username),
				FOREIGN KEY (restaurant) REFERENCES Restaurants(id)
		);''')

	print 'Creating Reviews table...'
	c.execute(
		'''CREATE TABLE Reviews (
                user		TEXT not null,
                restaurant	INTEGER not null,
                review		TEXT not null,
                timestamp	DATE not null,
                PRIMARY KEY (user, restaurant), -- one review per user per restaurant
                FOREIGN KEY (user) REFERENCES Users(username),
                FOREIGN KEY (restaurant) REFERENCES Restaurants(id)
        );''')

#populates fresh tables with mock data
def populate_tables(c):
	populate_users(c)
	populate_restaurants(c)
	populate_ratings(c)

#populates users table with random name & email
#username created based on first name
#uses simple-to-use passwords for testing purposes
def populate_users(c):
	print 'Populating Users table...'

	required = ['names.txt', 'emails.txt']
	for f in required:
		if not (os.access(f, os.R_OK) and os.path.isfile(f)):
			print >>sys.stderr, "Error: cannot access raw data file '%s'" %f
			sys.exit(1)

	names = open('names.txt').readlines()
	emails = open('emails.txt').readlines()
	passwords = ['qwerty', '1111', 'zzz', 'abc', 'hello', '555', 'qqq', 'ppp']

	for name in names:
		full_name = name.rstrip()
		username = full_name.split(' ')[0].lower() + str(random.randint(10, 99)) #first name + 2 digits
		password = passwords[random.randint(0, len(passwords) - 1)]
		email = emails.pop().strip()
		data = (full_name, username, password, email, 'active')
		c.execute('''INSERT INTO Users (full_name, username, password, email, status)
				VALUES (?, ?, ?, ?, ?)''', data)

#populates restaurants table
def populate_restaurants(c):
	print 'Populating Restaurants table...'

	if not (os.access('restaurants', os.R_OK) and os.path.isdir('restaurants')):
		print >>sys.stderr, "Error: cannot access raw data directory 'restaurants'"
		sys.exit(1)

	if not (os.access('suburbs.txt', os.R_OK) and os.path.isfile('suburbs.txt')):
		print >>sys.stderr, "Error: cannot access raw data file 'suburbs.txt'"
		sys.exit(1)

	#get postcodes from file and cache in dict
	suburbs = open('suburbs.txt').readlines()
	postcodes = {}
	for suburb in suburbs:
		lat, lng, pst, sub = suburb.strip().split('\t')
		postcodes[sub] = pst
	postcodes['CBD'] = 2000 #special case not in data file

	users = c.execute('SELECT username FROM Users').fetchall()
	num_users = c.execute('SELECT COUNT(*) FROM Users').fetchone()[0]

	i = 0
	for restaurant in glob.glob('restaurants/*'):
		r = open(restaurant).readlines()

		#extract info from file
		try:
			name = r[0].strip()
			name = HTMLParser().unescape(name)
			address = r[1].strip()
			address = HTMLParser().unescape(address)
			address = re.sub(r'nsw', 'NSW', address, flags=re.I)
			if not address.endswith(', NSW'):
				address = address + ', NSW'
			suburb = re.match(r'.*, (.+), Sydney', r[1]).group(1)
			suburb = HTMLParser().unescape(suburb)
			phone = r[2].strip().replace('(', '').replace(')', '')
			if re.match('Not available', phone):
				phone = 'Not available'
			hours = r[3].strip()
			hours = re.sub(r'\s*,\s*', ', ', hours)
			cuisine = r[4].strip()
			cost = r[5].strip()
			image = r[6].strip()
		except:
			print >>sys.stderr, "Error: skipping '%s'" %restaurant
			continue

		#lookup postcode using suburb
		postcode = ''
		if not suburb in postcodes:
			continue
		else:
			postcode = postcodes[suburb]

		#and append it to the address
		address = address + ' ' + str(postcode)

		#chose a random protocol for the website
		protocol = 'http://'
		if random.randint(0, 1) == 1:
			protocol = 'https://'

		#make site of the form protocol://www.lowercase.name.of.restaurant.fake.com
		website = name.replace(' ', '.').replace('-', '').lower().strip().replace('..', '.') + '.fake.com'
		website = HTMLParser().unescape(website)
		website = urllib.quote(website) #encode as url
		website = protocol + 'www.' + website #avoid encoding the protocol

		#ensure only some restaurants have owners
		owner = None
		if random.randint(0, 3) == 0:
			owner = users[random.randint(0, num_users - 1)][0]

		i += 1
		data = (i, name, suburb, address, postcode, phone, hours, cuisine, owner, website, cost, image)
		c.execute('''INSERT INTO Restaurants
				(id, name, suburb, address, postcode, phone, hours, cuisine, owner, website, cost, image)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)

#populates ratings table
def populate_ratings(c):
	print 'Populating Ratings table...'

	users = c.execute('SELECT username FROM Users').fetchall()
	num_users = c.execute('SELECT COUNT(*) FROM Users').fetchone()[0]
	restaurants = c.execute('SELECT id FROM Restaurants').fetchall()
	num_restaurants = c.execute('SELECT COUNT(*) FROM Restaurants').fetchone()[0]

	#add 1000 random ratings by 1000 random users to 1000 random restaurants
	#assumes there is enough data in users and restaurants tables
	i = 0
	while i < 1000:
		user = users[random.randint(0, num_users - 1)][0]
		restaurant = restaurants[random.randint(0, num_restaurants - 1)][0]

		#use a ficticious rating between 1 and 5
		int_part = str(random.randint(1, 4))
		decimal_part = str(random.randint(1, 9))
		rating = float(int_part + '.' + decimal_part)

		data = (user, restaurant, rating)
		try:
			c.execute('''INSERT INTO Ratings (user, restaurant, rating) VALUES (?, ?, ?)''', data)
			i += 1
		except:
			pass #skip this since only one rating per user per restaurant

if __name__ == '__main__':
	main()
