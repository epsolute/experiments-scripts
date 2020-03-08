#!/usr/bin/env python3

import random
import time
import math
from enum import Enum, auto


class Engine(Enum):
	kalepso = 3306
	mariadb = 3307
	oracle = 1521
	microsoft = 1433

	def __str__(self):
		return self.name

	@staticmethod
	def valueForParse(key):
		try:
			return Engine[key]
		except KeyError:
			raise ValueError()


def parse():
	import argparse

	inputSizeDefault = 1000
	inputSizeMin = 100
	inputSizeMax = 247000
	
	rangeSizeDefault = 10
	rangeSizeMin = 2
	rangeSizeMax = 1000

	def argcheckInputSize(value):
		number = int(value)
		if number < inputSizeMin or number > inputSizeMax:
			raise argparse.ArgumentTypeError(f"Input size must be {inputSizeMin} to {inputSizeMax}. Given {number}")
		return number

	def argcheckInputMax(value):
		number = int(value)
		if number <= 0:
			raise argparse.ArgumentTypeError(f"Input max must be above 0. Given {number}")
		return number

	def argcheckRange(value):
		number = int(value)
		if number < 2 or number > 1000:
			raise argparse.ArgumentTypeError(f"Input / queries size must be {rangeSizeMin} to {rangeSizeMax}. Given {number}")
		return number

	parser = argparse.ArgumentParser(description="Run simple uniform range queries on Kalepso.")

	parser.add_argument("--size", dest="size", metavar="input-size", type=argcheckInputSize, required=False, default=inputSizeDefault, help=f"The size of data [{inputSizeMin} - {inputSizeMax}]")
	parser.add_argument("--queries", dest="queries", metavar="queries-size", type=argcheckInputSize, required=False, default=int(inputSizeDefault / 10), help=f"The number of queries [{inputSizeMin} - {inputSizeMax}]")
	parser.add_argument("--range", dest="range", metavar="range-size", type=argcheckRange, required=False, default=10, help=f"The range size [{rangeSizeMin} - {rangeSizeMax}]")

	parser.add_argument("--seed", dest="seed", metavar="seed", type=int, default=123456, required=False, help="Seed to use for PRG")

	parser.add_argument('--engine', dest="engine", metavar="engine", type=Engine.valueForParse, choices=list(Engine), required=True, help="Engine to run benchmark against")

	args = parser.parse_args()

	random.seed(args.seed)

	return args.size, args.range, args.queries, args.engine


def generateLoads(dataSize, queryRange, queriesSize):
	import pandas as pd

	data = pd.read_csv("https://gist.githubusercontent.com/dbogatov/a192d00d72de02f188c5268ea1bbf25b/raw/b1e7ea9e058e7906e0045b29ad75a5f201bd4f57/state-of-california-2019.csv")
	# data = pd.read_csv("data.csv")
	
	sampled = data.sample(frac = float(dataSize) / len(data.index))

	queries = []
	
	for i in range(1, queriesSize):
		left = random.randint(0, int(sampled["Total Pay & Benefits"].max()) - queryRange)
		queries += [(left, left + queryRange)]

	return sampled, queries

def runLoadsMySQL(data, queries, port):
	import mysql.connector as mysql

	db = mysql.connect(
		host="localhost",
		user="root",
		port=port,
		passwd="kalepso"
	)

	cursor = db.cursor()
	cursor.execute("CREATE DATABASE IF NOT EXISTS CA_public_employees_salaries_2019")
	cursor.execute("USE CA_public_employees_salaries_2019")
	cursor.execute("DROP TABLE IF EXISTS salaries")
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS salaries (
			fullname VARCHAR(100),		# Employee Name
			jobtitle VARCHAR(100),		# Job Title
			salary FLOAT,				# Base Pay
			overtimepay FLOAT,			# Overtime Pay
			other FLOAT,				# Other Pay
			benefits FLOAT NULL,		# Benefits
			total FLOAT,				# Total Pay
			totalPlusBenefits FLOAT,	# Total Pay & Benefits
			year INT,					# Year
			notes VARCHAR(150) NULL,	# Notes
			agency VARCHAR(100),		# Agency
			status VARCHAR(30),			# Status
			
			INDEX totalPlusBenefitsIndex (totalPlusBenefits)
		)
	""")
	cursor.execute("SET SESSION query_cache_type=0")

	db.commit()

	init = time.time()

	insert = """
		INSERT INTO salaries 
			(fullname, jobtitle, salary, overtimepay, other, benefits, total, totalPlusBenefits, year, notes, agency, status) 
		VALUES 
			(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
	"""
	for index, record in data.iterrows():
		cursor.execute(
			insert,
			(
				record["Employee Name"],
				record["Job Title"],
				float(record["Base Pay"]),
				float(record["Overtime Pay"]),
				float(record["Other Pay"]),
				0.0 if record["Benefits"] == "Not Provided" else float(record["Benefits"]),
				float(record["Total Pay"]),
				float(record["Total Pay & Benefits"]),
				int(record["Year"]),
				"" if math.isnan(record["Notes"]) else record["Notes"],
				record["Agency"],
				"" if math.isnan(record["Status"]) else record["Status"]
			)
		)
		db.commit()

	inserted = time.time()

	query = "SELECT * FROM salaries WHERE totalPlusBenefits BETWEEN %s AND %s"
	for rangeQuery in queries:
		cursor.execute(query, rangeQuery)
		records = cursor.fetchall()

	queried = time.time()
	
	sizeQuery = """
		SELECT
			ROUND((DATA_LENGTH + INDEX_LENGTH)) AS `Size (B)`
		FROM
			information_schema.TABLES
		WHERE
			TABLE_SCHEMA = "CA_public_employees_salaries_2019"
		AND
			TABLE_NAME = "salaries"
		ORDER BY
			(DATA_LENGTH + INDEX_LENGTH)
		DESC
	"""

	cursor.execute(sizeQuery)
	size = int(cursor.fetchall()[0][0])

	return inserted - init, queried - inserted, size


def runLoadsOracle(data, queries, port):
	import cx_Oracle

	connection = cx_Oracle.connect("dmytro", "password", f"0.0.0.0:{port}/ORCLCDB.localdomain")

	cursor = connection.cursor()

	cursor.execute("BEGIN EXECUTE IMMEDIATE 'DROP TABLE ranges'; EXCEPTION WHEN OTHERS THEN NULL; END;")
	cursor.execute("CREATE TABLE ranges (point NUMBER ENCRYPT NO SALT)")
	cursor.execute("CREATE INDEX pointIndex on ranges (point)")

	connection.commit()

	init = time.time()

	insert = "INSERT INTO ranges (point) VALUES (:point)"
	for point in data:
		cursor.execute(insert, point=point)
		connection.commit()

	inserted = time.time()

	query = "SELECT point FROM ranges WHERE point BETWEEN :low AND :high"
	for rangeQuery in queries:
		cursor.execute(query, low=rangeQuery[0], high=rangeQuery[1])
		records = cursor.fetchall()
		# print(f"For range {rangeQuery}, the result is {len(records)} records")

	queried = time.time()

	return inserted - init, queried - inserted


def generateMSSQLLoad(data, queries):

	print(len(data))
	print(len(queries))
	for point in data:
		print(point)

	for query in queries:
		print(f"{query[0]} {query[1]}")


if __name__ == "__main__":

	dataSize, queryRange, queriesSize, engine = parse()
	data, queries = generateLoads(dataSize, queryRange, queriesSize)

	if engine == Engine.microsoft:
		generateMSSQLLoad(data, queries)
	else:
		if engine == Engine.kalepso or engine == Engine.mariadb:
			insertionTime, queryTime, tableSize = runLoadsMySQL(data, queries, engine.value)
		else:
			insertionTime, queryTime, tableSize = runLoadsOracle(data, queries, engine.value)
		print(f"For {engine}: inserted in {int(insertionTime * 1000)} ms, queries in {int(queryTime * 1000)} ms, database size is {tableSize} bytes")
