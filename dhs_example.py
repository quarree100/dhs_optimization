"""
oemof application for research project quarree100.

Based on the excel_reader example of oemof_examples repository:
https://github.com/oemof/oemof-examples

Copyright (c) 2019 Johannes Röder <jroeder@uni-bremen.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

__copyright__ = "Johannes Röder <jroeder@uni-bremen.de>"
__license__ = "GPLv3"

from oemof.tools import logger, helpers
import oemof.solph as solph
import oemof.outputlib as outputlib
import logging
import pandas as pd
from simpledbf import Dbf5
from modules.dhs_nodes import add_nodes_dhs, add_nodes_houses


# get data
# infrastructure data

df_points = Dbf5('data/gis/Points_all_hombeer.dbf').to_dataframe()
df_lines = Dbf5('data/gis/Lines_all_hombeer.dbf').to_dataframe()

qgis_data = {'points': df_points,
             'lines': df_lines}

# house data
# getting general data for houses (same for all houses)
xls = pd.ExcelFile('data/data_houses.xlsx')
houses_general = {'bus': xls.parse('Buses'),
                  'source': xls.parse('Sources'),
                  'demand': xls.parse('Demand'),
                  'transformer': xls.parse('Transformer'),
                  'storages': xls.parse('Storages')}

# individual house data (will be replaced by kataster Daten)
houses_individual = df_points.loc[df_points['type'] == 'H']
houses_individual = houses_individual.reset_index(drop=True)

# data for demand series of houses
xls = pd.ExcelFile('data/Timeseries_houses.xlsx')
houses_series = {'heat': xls.parse('heat')}

# put all house data together
data_houses = {'general_data': houses_general,
               'individual_data': houses_individual,
               'series_data': houses_series}

# generation data

# getting general data for generation (same for all generation)
xls = pd.ExcelFile('data/data_generation.xlsx')
generation_general = {'bus': xls.parse('Buses'),
                      'source': xls.parse('Sources'),
                      'demand': xls.parse('Demand'),
                      'transformer': xls.parse('Transformer'),
                      'storages': xls.parse('Storages')}

# individual house data
generation_individual = df_points.loc[df_points['type'] == 'G']
generation_individual = generation_individual.reset_index(drop=True)

# data for demand series of generation
generation_series = {}

# put all house data together
data_generation = {'general_data': generation_general,
                   'individual_data': generation_individual,
                   'series_data': generation_series}

xls = pd.ExcelFile('data/data_heatpipes.xlsx')
gd_infra = {'heatpipe_options': xls.parse('Heatpipes')}

# general data

num_ts = 6    # number of timesteps
time_res = 1    # time resolution: [1/h] (percentage of hour)
                # => 0.25 is quarter-hour resolution

gd = {'num_ts': num_ts,
      'time_res': time_res,
      'rate': 0.01,
      'f_invest': num_ts/(8760 / time_res),
      # 'f_invest': 1,
      }

# defining empty dict for nodes
nodes = []  # list of all nodes
buses = {}   # dict of all buses

# Setup and Solve Energy System ###############################################

logger.define_logging()
logging.info('Initialize the energy system')

date_time_index = pd.date_range('1/1/2018', periods=num_ts, freq='H')
esys = solph.EnergySystem(timeindex=date_time_index)

logging.info('Create oemof objects')

# add heating infrastructure
nodes, buses = add_nodes_dhs(qgis_data, gd, gd_infra, nodes, buses)
logging.info('DHS Nodes appended.')

# # add houses
nodes, buses = add_nodes_houses(gd, data_houses, nodes, buses, 'house')
logging.info('HOUSE Nodes appended.')

# add generation sites
nodes, buses = add_nodes_houses(gd, data_generation, nodes, buses,
                                'generation')
logging.info('GENERATION Nodes appended.')

# add nodes and flows to energy system
esys.add(*nodes)

logging.info('Energysystem has been created')
print("*********************************************************")
print("The following objects have been created from excel sheet:")
for n in esys.nodes:
    oobj =\
        str(type(n)).replace("<class 'oemof.solph.", "").replace("'>", "")
    print(oobj + ':', n.label)
print("*********************************************************")

logging.info('Build the operational model')
om = solph.Model(esys)

logging.info('Solve the optimization problem')
om.solve(solver='gurobi', solve_kwargs={'tee': True})

# # plot the Energy System
# try:
#     import pygraphviz
#     import graph_model as gm
#     from oemof.graph import create_nx_graph
#     import networkx as nx
#     grph = create_nx_graph(esys)
#     pos = nx.drawing.nx_agraph.graphviz_layout(grph, prog='neato')
#     gm.plot_graph(pos, grph)
#     plt.show()
#     logging.info('Energy system Graph OK')
# except ImportError:
#     logging.info('Module pygraphviz not found: Graph was not plotted.')

esys.results['main'] = outputlib.processing.results(om)
results = esys.results['main']

# Add results to dataframe of line layer
l_heatpipes = []
l_hp_invest = []

for n in esys.nodes:
    type_name =\
        str(type(n)).replace("<class 'modules.oemof_heatpipe.", "").replace(
            "'>", "")
    if type_name == "HeatPipeline":
        l_heatpipes.append(str(n.label).split('heatpipe_x_')[1])
        # p_invest = outputlib.views.node(results, n.label)['scalars'][0]
        # print(p_invest)
        l_hp_invest.append(outputlib.views.node(
            results, str(n.label))['scalars'][0])

d_heatpipes_results = {'dir_1': l_heatpipes,
                       'size_1': l_hp_invest}

df_hp_result = pd.DataFrame(d_heatpipes_results)

# preparing the results (maximum installed capacity of bi-directional trafos)
df_lines['dir_1'] = df_lines['id_start'] + '-' + df_lines['id_end']
df_lines = df_lines.merge(df_hp_result, on='dir_1', how='left')
df_hp_result = df_hp_result.rename(
    index=str, columns={"dir_1": "dir_2", "size_1": "size_2"})
df_lines['dir_2'] = df_lines['id_end'] + '-' + df_lines['id_start']
df_lines = df_lines.merge(df_hp_result, on='dir_2', how='left')
df_lines['size_1'].fillna(0, inplace=True)
df_lines['size_2'].fillna(0, inplace=True)
df_lines['size'] = round(df_lines['size_1'] + df_lines['size_2'])

# look-up table for size classes - example for given pressure loss and delta T
df_lookup = pd.DataFrame(data=[[0, 0.1, '0'],
                               [0.1, 20, 'DN 20'],
                               [20.1, 30, 'DN 25'],
                               [30.1, 54, 'DN 32'],
                               [54.1, 90, 'DN 40'],
                               [90.1, 156, 'DN 50'],
                               [156.1, 300, 'DN 65'],
                               [300.1, 507, 'DN 80'],
                               [507.1, 900, 'DN 100'],
                               [900.1, 1630, 'DN 125'],
                               [1630.1, 2660, 'DN 150'],
                               [2660.1, 5850, 'DN 200']],
                         columns=['min', 'max', 'DN'])

df_lines['size_class'] = pd.cut(
    df_lines['size'],
    bins=[0] + df_lookup[['min','max']].stack()[1::2].tolist(),
    labels=df_lookup['DN'].tolist())

# export results
df_lines.to_csv('data/gis/results_grid_hombeer.csv')

# ################ geoplot ################################################

# geo-plot the Energy System
try:
    import geopandas as gpd
    from matplotlib import pyplot as plt

    # read existing line layer, which was input for oemof
    gdf_lines = gpd.read_file('data/gis/Lines_all_hombeer.shp')
    gdf_lines['id'] = gdf_lines['id_start'] + gdf_lines['id_end']

    # read oemof results for heatpipelines invest
    df_results = pd.read_csv('data/gis/results_grid_hombeer.csv', index_col=0)
    df_results['id'] = df_results['id_start'] + df_results['id_end']

    gdf_lines = gdf_lines.merge(df_results[['id', 'size', 'size_class']],
                                on='id')

    gdf_points = gpd.read_file('data/gis/Points_all_hombeer.shp')

    # make it a bit nicer using a dictionary to assign colors and line widths
    line_attrs = {'DN 200': ['red', 4],
                  'DN 150': ['red', 4],
                  'DN 125': ['red', 4],
                  'DN 100': ['red', 4],
                  'DN 80': ['darkred', 3.5],
                  'DN 65': ['red', 3],
                  'DN 50': ['orangered', 2.5],
                  'DN 40': ['darkorange', 2],
                  'DN 32': ['orange', 1.5],
                  'DN 25': ['orange', 1.1],
                  'DN 20': ['orange', 0.8],
                  '0': ['black', 0],
                  }

    # plot the data
    fig, ax = plt.subplots(
        # figsize=(12, 8)
        )

    for ctype, data in gdf_lines.groupby('size_class'):
        data.plot(color=line_attrs[ctype][0],
                  label=ctype,
                  ax=ax,
                  linewidth=line_attrs[ctype][1])

    # ax = gdf_lines.plot(color='blue')
    gdf_points.plot(ax=ax, color='grey')
    fig.legend()

    logging.info('Energy system Geo-plot OK')

except ImportError:
    logging.info('Module geopandas not found: Geo-plot was not plotted.')

# plot installed transformer capacity
flows = [x for x in results.keys() if x[1] is not None]
flows_invest = [x for x in flows if hasattr(
    results[x]['scalars'], 'invest')]
flows_invest_boiler = [x for x in flows_invest if 'boiler' in x[0].label[2]]
flows_invest_boiler_generation = [x for x in flows_invest_boiler
                                  if 'generation' in x[0].label[0]]
flows_invest_boiler_houses = [x for x in flows_invest_boiler
                              if 'house' in x[0].label[0]]

p_gen_invest = 0
p_house_invest = 0

for h in flows_invest_boiler_houses:
    p_house_invest += results[h]['scalars']['invest']
for g in flows_invest_boiler_generation:
    p_gen_invest += results[g]['scalars']['invest']

df_invest = pd.DataFrame([p_gen_invest, p_house_invest],
                         index=['zentral', 'dezentral'],
                         columns=['Installierte Leistung [kW]'])
fig2, ax = plt.subplots()
df_invest.plot(ax=ax, kind='bar')
fig2.tight_layout()
