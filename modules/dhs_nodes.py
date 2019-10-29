"""
oemof application for research project quarree100.

Based on the excel_reader example of oemof_examples repository:
https://github.com/oemof/oemof-examples

Copyright (c) 2019 Johannes Röder <jroeder@uni-bremen.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

__copyright__ = "Johannes Röder <jroeder@uni-bremen.de>"
__license__ = "GPLv3"

import oemof.solph as solph
from modules import oemof_heatpipe as oh, add_components as ac


def add_nodes_dhs(geo_data, gd, gd_infra, nodes, busd):
    """
    :param geo_data: geometry data (points and line layer from qgis)
    :param gd: general data
    :param gd_infra: general data for infrastructure nodes
    :param nodes: list of nodes for oemof
    :param busd: dict of buses for building nodes
    :return:    nodes - updated list of nodes
                busd - updated list of buses
    """

    d_labels = {}

    # add heat buses for all nodes
    for n, o in geo_data['points'].iterrows():

        d_labels['l_2'] = 'heat'
        d_labels['l_3'] = 'bus'
        d_labels['l_4'] = o['id']

        if o['type'] == 'H':
            d_labels['l_1'] = 'house'

        if o['type'] == 'K':
            d_labels['l_1'] = 'infrastructure'

        if o['type'] == 'G':
            d_labels['l_1'] = 'generation'

        l_bus = oh.Label(d_labels['l_1'], d_labels['l_2'], d_labels['l_3'],
                         d_labels['l_4'])
        bus = solph.Bus(label=l_bus)
        nodes.append(bus)

        busd[l_bus] = bus

    # add heatpipes for all lines
    for p, q in geo_data['lines'].iterrows():

        d_labels['l_1'] = 'infrastructure'
        d_labels['l_2'] = 'heat'

        # connection of houses
        if q['type'] == "HL":

            if q['id_start'][:1] == "H":
                start = q['id_end']
                end = q['id_start']
                b_in = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', start)]
                b_out = busd[('house', d_labels['l_2'], 'bus', end)]

            else:
                start = q['id_start']
                end = q['id_end']
                b_in = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', start)]
                b_out = busd[('house', d_labels['l_2'], 'bus', end)]

            d_labels['l_4'] = start + '-' + end

            nodes, busd = ac.add_heatpipes(
                gd_infra['heatpipe_options'], d_labels, gd, q, b_in, b_out,
                nodes, busd)

        # connection energy generation site
        if q['type'] == "GL":

            if q['id_start'][:1] == "G":
                start = q['id_start']
                end = q['id_end']
                b_in = busd[('generation', d_labels['l_2'], 'bus', start)]
                b_out = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', end)]

            else:
                start = q['id_end']
                end = q['id_start']
                b_in = busd[('generation', d_labels['l_2'], 'bus', start)]
                b_out = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', end)]

            d_labels['l_4'] = start + '-' + end

            nodes, busd = ac.add_heatpipes(
                gd_infra['heatpipe_options'], d_labels, gd, q, b_in, b_out,
                nodes, busd)

        # connection of knots with 2 pipes in each direction since flow
        # direction is unknown
        if q['type'] == "DL":

            start = q['id_start']
            end = q['id_end']
            b_in = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', start)]
            b_out = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', end)]

            d_labels['l_4'] = start + '-' + end

            nodes, busd = ac.add_heatpipes(
                gd_infra['heatpipe_options'], d_labels, gd, q, b_in, b_out,
                nodes, busd)

            start = q['id_end']
            end = q['id_start']
            b_in = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', start)]
            b_out = busd[(d_labels['l_1'], d_labels['l_2'], 'bus', end)]

            d_labels['l_4'] = start + '-' + end

            nodes, busd = ac.add_heatpipes(
                gd_infra['heatpipe_options'], d_labels, gd, q, b_in, b_out,
                nodes, busd)

    return nodes, busd


def add_nodes_houses(gd, data_objects, nodes, busd, label_1):

    ind_data = data_objects['individual_data']
    series = data_objects['series_data']
    d_labels = {}

    for r, c in ind_data.iterrows():

        d_labels['l_1'] = label_1
        d_labels['l_4'] = c['id']

        # add buses first, because other classes need to have them already
        nodes, busd = ac.add_buses(data_objects['general_data']['bus'],
                                   d_labels, nodes, busd)

        for key, item in data_objects['general_data'].items():

            # if key == 'bus':
            #     nodes, busd = ac.add_buses(item, d_labels, nodes, busd)

            if key == 'source':
                nodes, busd = ac.add_sources(item, d_labels, gd, nodes, busd)

            if key == 'demand':
                nodes, busd = ac.add_demand(item, d_labels, gd, series, nodes,
                                            busd)

            if key == 'transformer':
                nodes, busd = ac.add_transformer(item, d_labels, gd, nodes,
                                                 busd)

            if key == 'storages':
                nodes, busd = ac.add_storage(item, d_labels, gd, nodes, busd)

    return nodes, busd
