import sys

import networkx
from bs4 import BeautifulSoup
import os
import shutil
import itertools
import copy
from collections import defaultdict
from dataclasses import dataclass, field


# Tags Attributes:
CLASS_TA = 'class'
ID_TA = 'id'
TITLE_TA = 'title'
CONNECTIVITY_TA = 'connectivity'

# Class types
GRAPH_CT = 'graph'
LEGEND_MISC_CT = 'conn_legend_misc'
BACKGROUND_CT = 'background'
NAMESPACE_CT = 'cluster'
NODE_CT = 'node'
EDGE_CT = 'edge'
CONNECTIVITY_CT = 'connectivity'


def set_tags_info(soup):
    # wrap the title + background polygon with an <a>:
    graph_polygon = soup.svg.polygon
    graph_polygon = graph_polygon.wrap(soup.new_tag('a'))
    graph_polygon[CLASS_TA] = BACKGROUND_CT
    graph_text = soup.svg.find('text')
    graph_polygon.append(graph_text)

    # update class to connectivities:
    conn_legend = soup.svg.find('title', string='dict_box')
    if conn_legend:
        conn_legend = conn_legend.find_parent('g')
        conn_legend[CLASS_TA] = LEGEND_MISC_CT
        for conn in conn_legend.find_all('a'):
            conn[CLASS_TA] = CONNECTIVITY_CT
        for conn in conn_legend.find_all('g'):
            conn[CLASS_TA] = LEGEND_MISC_CT


    # for element that we want to add a link, we replace <g> with <a>:
    for tag in soup.svg.find_all('g'):
        if tag[CLASS_TA] not in [GRAPH_CT, LEGEND_MISC_CT]:
            tag.name = 'a'

    # add missing id and titles:
    for tag in soup.svg.find_all('a'):
        if tag[CLASS_TA] == BACKGROUND_CT:
            tag[ID_TA] = 'index'
            tag[TITLE_TA] = tag.find('text').string
        elif tag[CLASS_TA] == CONNECTIVITY_CT:
            short = tag.text.split()[0]
            conn_id = 'conn_' + short
            tag[ID_TA] = conn_id
            tag[TITLE_TA] = short
        else:
            tag[TITLE_TA] = tag.title.string

        # 3. set connectivity:
        if tag[CLASS_TA] == EDGE_CT and tag.find('text'):
            tag[CONNECTIVITY_TA] = tag.find('text').string
        elif tag[CLASS_TA] == NODE_CT and tag.title and 'clique' in tag.title.string:
            tag[CONNECTIVITY_TA] = tag.find_all('text')[1].string
        elif tag[CLASS_TA] == CONNECTIVITY_CT:
            tag[CONNECTIVITY_TA] = tag[TITLE_TA]


def get_tag_info(tag):
    t_id = tag[ID_TA]
    t_class = tag[CLASS_TA]
    t_title = tag[TITLE_TA]
    t_conn = tag.get(CONNECTIVITY_TA) if tag.get(CONNECTIVITY_TA) else ''
    return t_id, t_class, str(t_title), t_conn


def get_tags_info(soup):
    return [(get_tag_info(tag)) for tag in soup.svg.find_all('a')]

@dataclass
class ConnLegend:
    conns: dict = field(default_factory=dict)


@dataclass(unsafe_hash=True)
class Conn:
    t_id: str = ''


@dataclass
class Namespace:
    t_id: str
    name: str
    nodes: list = field(default_factory=list)


@dataclass
class Node:
    t_id: str
    name: str
    conn: Conn
    edges: list = field(default_factory=list)
    def real_node(self):
        return self.conn.t_id == ''


@dataclass
class Edge:
    t_id: str
    src_name: str
    dst_name: str
    conn: Conn
    src: Node = None
    dst: Node = None


@dataclass
class Clique:
    conn: Conn
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)


@dataclass
class BiClique:
    conn: Conn
    node: Node
    src_nodes: list = field(default_factory=list)
    src_edges: list = field(default_factory=list)
    dst_nodes: list = field(default_factory=list)
    dst_edges: list = field(default_factory=list)


@dataclass
class Graph:
    t_id: str = ''
    name: str = ''
    namespaces: dict = field(default_factory=dict)
    nodes: dict = field(default_factory=dict)
    edges: dict = field(default_factory=dict)
    cliques: list = field(default_factory=list)
    bicliques: list = field(default_factory=list)
    conn_legend = ConnLegend()


def create_graph_elements(tags_info):
    all_conns = set(t[3] for t in tags_info)
    graph = Graph()
    for t_conn in all_conns:
        graph.conn_legend.conns[t_conn] = Conn()
    for t_id, t_class, t_title, t_conn in tags_info:
        if t_class == BACKGROUND_CT:
            graph.t_id = t_id
            graph.name = t_title
        elif t_class == NAMESPACE_CT:
            namespace_name = t_title.replace('cluster_', '').replace('_namespace', '')
            graph.namespaces[namespace_name] = Namespace(t_id, namespace_name)
        elif t_class == NODE_CT:
            graph.nodes[t_title] = Node(t_id, t_title, graph.conn_legend.conns[t_conn])
        elif t_class == EDGE_CT:
            src_name, dst_name = t_title.split('->')
            graph.edges[(src_name, dst_name)] = Edge(t_id, src_name, dst_name, graph.conn_legend.conns[t_conn])
        elif t_class == CONNECTIVITY_CT:
            graph.conn_legend.conns[t_conn].t_id = t_id
    return graph


def connect_graph_elements(graph):
    for name, node in graph.nodes.items():
        node.edges = [edge for edge in graph.edges.values() if node.name in [edge.src_name, edge.dst_name]]
        namespace_name = node.name.split('/')[0].replace('-', '_')
        namespace = graph.namespaces.get(namespace_name, None)
        if namespace:
            namespace.nodes.append(node)

    for (src_name, dst_name), edge in graph.edges.items():
        edge.src = graph.nodes[src_name]
        edge.dst = graph.nodes[dst_name]

    all_cliques_nodes = [node for node in graph.nodes.keys() if node.startswith('clique_')]
    all_cliques_edges = [edge for edge in graph.edges.keys() if edge[0].startswith('clique_') and edge[1].startswith('clique_')]
    clqs_graph = networkx.Graph()
    clqs_graph.add_nodes_from(all_cliques_nodes)
    clqs_graph.add_edges_from(all_cliques_edges)
    clique_sets = networkx.connected_components(clqs_graph)

    for clique_set in clique_sets:
        clique_conn = graph.nodes[list(clique_set)[0]].conn
        clique = Clique(clique_conn)
        clique_set_names = clique_set
        clique.edges = [edge for edge in graph.edges.values() if edge.src_name in clique_set_names or edge.dst_name in clique_set_names]
        node_names = set(e.src_name for e in clique.edges) | set(e.dst_name for e in clique.edges)
        clique.nodes = [node for node in graph.nodes.values() if node.name in node_names]
        graph.cliques.append(clique)

    all_bicliques_nodes = [node for name, node in graph.nodes.items() if name.startswith('biclique_')]
    for biclique_node in all_bicliques_nodes:
        biclique = BiClique(biclique_node.conn, biclique_node)
        biclique.src_edges = [edge for edge in graph.edges.values() if edge.dst_name == biclique_node.name]
        biclique.dst_edges = [edge for edge in graph.edges.values() if edge.src_name == biclique_node.name]
        biclique.src_nodes = [edge.src for edge in biclique.src_edges]
        biclique.dst_nodes = [edge.dst for edge in biclique.dst_edges]
        graph.bicliques.append(biclique)


def get_tags_relations(graph, tags_info):
    relations = defaultdict(set)
    highlights = defaultdict(set)


    for tag_id in [tag_info[0] for tag_info in tags_info]:
        relations[tag_id].add(tag_id)
        highlights[tag_id].add(tag_id)
        relations[tag_id].add(graph.t_id)
        for c in graph.conn_legend.conns.values():
            relations[tag_id].add(c.t_id)
        relations[graph.t_id].add(tag_id)
        relations[tag_id] |= set(n.t_id for n in graph.nodes.values() if n.real_node())

    for namespace in graph.namespaces.values():
        for node in namespace.nodes:
            relations[node.t_id].add(namespace.t_id)

    for edge in graph.edges.values():
        relations[edge.t_id] |= relations[edge.src.t_id]
        relations[edge.t_id] |= relations[edge.dst.t_id]
        relations[edge.conn.t_id] |= relations[edge.t_id]

    for node in graph.nodes.values():
        for edge in node.edges:
            relations[node.t_id] |= relations[edge.t_id]

    for clique in graph.cliques:
        for el in clique.nodes + clique.edges:
            for e in clique.edges:
                relations[el.t_id] |= relations[e.t_id]
                relations[clique.conn.t_id] |= relations[e.t_id]
        clq_core = [n for n in clique.nodes if not n.real_node()] + clique.edges
        for cc in clq_core:
            highlights[cc.t_id].add(clique.conn.t_id)
        for cc1, cc2 in itertools.product(clq_core, clq_core):
            highlights[cc1.t_id].add(cc2.t_id)

    for biclique in graph.bicliques:
        dst_edges_relations = set().union(*[relations[e.t_id] for e in biclique.dst_edges])
        src_edges_relations = set().union(*[relations[e.t_id] for e in biclique.src_edges])
        for n in biclique.src_nodes:
            relations[n.t_id] |= dst_edges_relations
        for n in biclique.dst_nodes:
            relations[n.t_id] |= src_edges_relations
        for e in biclique.dst_edges + biclique.src_edges:
            relations[e.t_id] |= src_edges_relations
            relations[e.t_id] |= dst_edges_relations
        relations[biclique.conn.t_id] |= relations[biclique.node.t_id]
        biclq_core = biclique.dst_edges + biclique.src_edges + [biclique.node]
        for bcc in biclq_core:
            highlights[bcc.t_id].add(biclique.conn.t_id)
        for bcc1, bcc2 in itertools.product(biclq_core, biclq_core):
            highlights[bcc1.t_id].add(bcc2.t_id)

    for namespace in graph.namespaces.values():
        for node in namespace.nodes:
            relations[namespace.t_id] |= relations[node.t_id]

    for edge in graph.edges.values():
        highlights[edge.t_id].add(edge.conn.t_id)

    return relations, highlights


def create_output(soup, relations, highlights, output_dir):
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)
    os.mkdir(os.path.join(output_dir, 'elements'))
    for tag in soup.svg.find_all('a'):
        t_id, t_class, _, _ = get_tag_info(tag)
        if t_class == BACKGROUND_CT:
            tag_file_name = os.path.join(output_dir, t_id + '.svg')
        else:
            tag_file_name = os.path.join(output_dir, 'elements', t_id + '.svg')
        tag_soup = copy.copy(soup)
        ids = relations[t_id]
        for tag2 in tag_soup.svg.find_all('a'):
            t_id2, t_class2, _, _ = get_tag_info(tag2)
            if t_id2 not in ids:
                tag2.extract()
                continue
            if (t_class == BACKGROUND_CT and t_class2 == BACKGROUND_CT) or (t_class != BACKGROUND_CT and t_class2 != BACKGROUND_CT):
                tag2['xlink:href'] = t_id2 + '.svg'
            elif t_class == BACKGROUND_CT and t_class2 != BACKGROUND_CT:
                tag2['xlink:href'] = 'elements/' + t_id2 + '.svg'
            else:
                tag2['xlink:href'] = '../' + t_id2 + '.svg'

            if t_id2 in highlights[t_id]:
                if t_class2 == NODE_CT:
                    tag2.polygon['stroke-width'] = '5'
                if t_class2 == NAMESPACE_CT:
                    tag2.polygon['stroke-width'] = '5'
                    tag2['font-weight'] = 'bold'
                if t_class2 == EDGE_CT:
                    tag2.path['stroke-width'] = '3'
                    tag2['font-weight'] = 'bold'
                if t_class2 == CONNECTIVITY_CT:
                    tag2['text-decoration'] = 'underline'
                    tag2['font-weight'] = 'bold'
        with open(tag_file_name, 'wb') as tag_cvg_file:
            tag_cvg_file.write(tag_soup.prettify(encoding='utf-8'))

def main(argv=None):
    file_name = argv[1]
    with open(file_name) as cvg_file:
        soup = BeautifulSoup(cvg_file.read(), 'xml')

    set_tags_info(soup)
    tags_info = get_tags_info(soup)
    graph = create_graph_elements(tags_info)
    connect_graph_elements(graph)
    relations, highlights = get_tags_relations(graph, tags_info)
    output_dir = file_name + '_connectivity_dir'
    create_output(soup, relations, highlights, output_dir)


if __name__ == "__main__":
    main(sys.argv)


