#!/usr/bin/env python3


def main():
	import pandas as pd
	import numpy as np
	from bokeh.plotting import show
	from scipy.stats import norm
	import scipy.stats as stats
	from bokeh.io import export_svgs

	# data = pd.read_csv("https://gist.githubusercontent.com/dbogatov/a192d00d72de02f188c5268ea1bbf25b/raw/b1e7ea9e058e7906e0045b29ad75a5f201bd4f57/state-of-california-2019.csv")
	data = pd.read_csv("data.csv")
	data.sort_values("Total Pay & Benefits", axis=0, ascending=True, inplace=True, na_position='last')
	salaries = data["Total Pay & Benefits"]
	salaries = salaries[salaries.between(salaries.quantile(.05), salaries.quantile(.95))]

	hist, edges = np.histogram(salaries, density=True, bins=100)
	x = np.linspace(salaries.min(), salaries.max(), 200)

	mu, sigma = norm.fit(salaries)
	pdf = 1 / (sigma * np.sqrt(2 * np.pi)) * np.exp(-(x - mu)**2 / (2 * sigma**2))

	plot = make_plot("Total Pay & Benefits", hist, edges, x, pdf)

	show(plot)

	plot.output_backend = "svg"
	export_svgs(plot, filename="plot.svg")


def make_plot(title, hist, edges, x, pdf):
	from bokeh.plotting import figure, output_file, show

	p = figure(title=title, tools='', background_fill_color="#fafafa")
	p.quad(top=hist, bottom=0, left=edges[:-1], right=edges[1:], fill_color="navy", line_color="white", alpha=0.5)
	p.line(x, pdf, line_color="#ff8888", line_width=4, alpha=0.7, legend_label="Normal PDF")

	p.y_range.start = 0
	p.xaxis.axis_label = 'salary'
	p.yaxis.axis_label = 'Pr(salary)'
	p.grid.grid_line_color = "white"

	p.left[0].formatter.use_scientific = False
	p.xaxis[0].formatter.use_scientific = False

	return p


if __name__ == "__main__":
	main()
