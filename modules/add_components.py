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
from oemof.tools import economics
from modules import oemof_heatpipe as oh


def add_buses(it, labels, nodes, busd):
    """
    :param it:  pd.Dataframe containing tabular information for the creation of
                buses
    :param labels: dict of label strings
    :return:
    """

    for i, b in it.iterrows():

        labels['l_3'] = 'bus'

        if b['active']:
            labels['l_2'] = b['label_2']
            l_bus = oh.Label(labels['l_1'], labels['l_2'], labels['l_3'],
                          labels['l_4'])

            # check if bus already exists (due to infrastructure)
            if l_bus in busd:
                print('bus bereits vorhanden:', l_bus)

            else:
                bus = solph.Bus(label=l_bus)
                nodes.append(bus)

                busd[l_bus] = bus

                if b['excess']:
                    labels['l_3'] = 'excess'
                    nodes.append(
                        solph.Sink(label=oh.Label(labels['l_1'], labels['l_2'],
                                               labels['l_3'], labels['l_4']),
                                   inputs={busd[l_bus]: solph.Flow(
                                       variable_costs=b['excess costs'])}))

                if b['shortage']:
                    labels['l_3'] = 'shortage'
                    nodes.append(
                        solph.Source(label=oh.Label(labels['l_1'], labels['l_2'],
                                                 labels['l_3'], labels['l_4']),
                                     outputs={busd[l_bus]: solph.Flow(
                                         variable_costs=b['shortage costs'])}))

    return nodes, busd


def add_sources(it, labels, gd, nodes, busd):

    for i, cs in it.iterrows():
        labels['l_3'] = 'source'

        if cs['active']:
            labels['l_2'] = cs['label_2']
            outflow_args = {}

            if cs['cost_series']:
                print('error: noch nicht angepasst!')

            else:
                outflow_args['variable_costs'] = cs['variable costs']

            nodes.append(
                solph.Source(
                    label=oh.Label(labels['l_1'], labels['l_2'],
                                     labels['l_3'], labels['l_4']),
                    outputs={busd[(
                        labels['l_1'], cs['label_2'], 'bus',
                        labels['l_4'])]: solph.Flow(**outflow_args)}))

    return nodes, busd


def add_demand(it, labels, gd, series, nodes, busd):

    for i, de in it.iterrows():
        labels['l_3'] = 'demand'

        if de['active']:
            labels['l_2'] = de['label_2']
            # set static inflow values
            inflow_args = {'nominal_value': de['scalingfactor'],
                           'fixed': de['fixed'],
                           'actual_value': series[
                               labels['l_2']][labels['l_4']]}

            # create
            nodes.append(
                solph.Sink(label=oh.Label(labels['l_1'], labels['l_2'],
                                       labels['l_3'], labels['l_4']),
                           inputs={
                               busd[(labels['l_1'], labels['l_2'], 'bus',
                                     labels['l_4'])]: solph.Flow(
                                        **inflow_args)}))

    return nodes, busd


def add_transformer(it, labels, gd, nodes, busd):

    for i, t in it.iterrows():
        labels['l_2'] = None

        if t['active']:
            labels['l_3'] = t['label_3']

            # Transformer with 1 Input and 1 Output
            if t['type'] == "1-in_1-out":

                b_in_1 = busd[(labels['l_1'], t['in_1'], 'bus', labels['l_4'])]
                b_out_1 = busd[(labels['l_1'], t['out_1'], 'bus',
                                labels['l_4'])]

                if t['invest']:

                    if t['eff_out_1'] == 'series':
                        print('noch nicht angepasst!')

                    # calculation epc
                    epc_t = economics.annuity(capex=t['capex'], n=t['n'],
                                              wacc=gd['rate']) * gd['f_invest']

                    # create
                    nodes.append(
                        solph.Transformer(
                            label=oh.Label(labels['l_1'], labels['l_2'],
                                        labels['l_3'], labels['l_4']),
                            inputs={b_in_1: solph.Flow()},
                            outputs={b_out_1: solph.Flow(
                                variable_costs=t['variable_costs'],
                                summed_max=t['in_1_sum_max'],
                                investment=solph.Investment(
                                    ep_costs=epc_t +
                                             t['service'] * gd['f_invest'],
                                    maximum=t['max_invest'],
                                    minimum=t['min_invest']))},
                            conversion_factors={
                                b_out_1: t['eff_out_1']}))

                else:
                    # create
                    if t['eff_out_1'] == 'series':
                        print('noch nicht angepasst!')
                        # for col in nd['timeseries'].columns.values:
                        #     if col.split('.')[0] == t['label']:
                        #         t[col.split('.')[1]] = nd['timeseries'][
                        #             col]

                    nodes.append(
                        solph.Transformer(
                            label=oh.Label(labels['l_1'], labels['l_2'],
                                        labels['l_3'], labels['l_4']),
                            inputs={b_in_1: solph.Flow()},
                            outputs={b_out_1: solph.Flow(
                                nominal_value=t['installed'],
                                summed_max=t['in_1_sum_max'],
                                variable_costs=t['variable_costs'])},
                            conversion_factors={b_out_1: t['eff_out_1']}))

    return nodes, busd


def add_storage(it, labels, gd, nodes, busd):

    for i, s in it.iterrows():
        if s['active']:

            label_storage = oh.Label(labels['l_1'], s['bus'], s['label'],
                                  labels['l_4'])
            label_bus = busd[(labels['l_1'], s['bus'], 'bus', labels['l_4'])]

            if s['invest']:

                epc_s = economics.annuity(
                    capex=s['capex'], n=s['n'],
                    wacc=gd['rate']) * gd['f_invest']

                nodes.append(
                    solph.components.GenericStorage(
                        label=label_storage,
                        inputs={label_bus: solph.Flow()},
                        outputs={label_bus: solph.Flow()},
                        loss_rate=s['capacity_loss'],
                        invest_relation_input_capacity=s[
                            'invest_relation_input_capacity'],
                        invest_relation_output_capacity=s[
                            'invest_relation_output_capacity'],
                        inflow_conversion_factor=s['inflow_conversion_factor'],
                        outflow_conversion_factor=s[
                            'outflow_conversion_factor'],
                        investment=solph.Investment(ep_costs=epc_s)))

            else:
                nodes.append(
                    solph.components.GenericStorage(
                        label=label_storage,
                        inputs={label_bus: solph.Flow()},
                        outputs={label_bus: solph.Flow()},
                        loss_rate=s['capacity_loss'],
                        nominal_capacity=s['capacity'],
                        inflow_conversion_factor=s['inflow_conversion_factor'],
                        outflow_conversion_factor=s[
                            'outflow_conversion_factor']))

    return nodes, busd


def add_heatpipes(it, labels, gd, q, b_in, b_out, nodes, busd):

    for i, t in it.iterrows():

        if t['active']:

            # definition of tag3 of label -> type of pipe
            labels['l_3'] = t['label_3']

            epc_p = float(economics.annuity(
                capex=it['capex_pipes'].values,# * q['length'],
                n=it['n_pipes'].values, wacc=gd['rate'])) * gd['f_invest']

            # Heatpipe with binary variable
            if t['nonconvex']:

                epc_fix = float(economics.annuity(
                    capex=it['fix_costs'].values * q['length'],
                    n=it['n_pipes'].values, wacc=gd['rate']) * gd['f_invest'])

                nodes.append(oh.HeatPipeline(
                    label=oh.Label(labels['l_1'], labels['l_2'],
                                     labels['l_3'], labels['l_4']),
                    inputs={b_in: solph.Flow()},
                    outputs={b_out: solph.Flow(
                        nominal_value=None, investment=solph.Investment(
                            ep_costs=epc_p,
                            maximum=t['cap_max'],
                            minimum=t['cap_min'],
                            nonconvex=True,
                            offset=epc_fix,
                        ))},
                    heat_loss_factor=t['l_factor'],
                    length=q['length']))

            else:

                nodes.append(oh.HeatPipeline(
                    label=oh.Label(labels['l_1'], labels['l_2'],
                                     labels['l_3'], labels['l_4']),
                    inputs={b_in: solph.Flow()},
                    outputs={b_out: solph.Flow(
                        nominal_value=None, investment=solph.Investment(
                            ep_costs=epc_p,
                            maximum=t['cap_max'],
                            minimum=0,
                            nonconvex=False,
                        ))},
                    heat_loss_factor=t['l_factor'],
                    length=q['length']))

    return nodes, busd
