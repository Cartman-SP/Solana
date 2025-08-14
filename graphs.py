import json
import os
from pyvis.network import Network
import networkx as nx

def load_data(filename):
    with open(filename, 'r') as f:
        data = json.load(f)
    return data['data']

def build_graph(data):
    G = nx.DiGraph()
    
    for item in data:
        main_wallet = item['main']
        found_wallet = item['faund']
        G.add_node(main_wallet, label=main_wallet, title=main_wallet, shape='box')
        G.add_node(found_wallet, label=found_wallet, title=found_wallet, shape='box')
        G.add_edge(main_wallet, found_wallet)
    
    return G

def visualize_graph(G, output_file='wallet_tree.html'):
    net = Network(
        height='800px', 
        width='100%', 
        bgcolor='#222222', 
        font_color='white',
        directed=True,
        notebook=True
    )
    
    # Указываем путь к шаблонам
    try:
        net.path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    except:
        pass
    
    net.barnes_hut(
        gravity=-80000,
        central_gravity=0.3,
        spring_length=200,
        spring_strength=0.001,
        damping=0.09,
        overlap=0.1
    )
    
    net.from_nx(G)
    
    for node in net.nodes:
        node['borderWidth'] = 1
        node['borderWidthSelected'] = 2
        node['color'] = {
            'border': '#2B7CE9',
            'background': '#97C2FC',
            'highlight': {
                'border': '#2B7CE9',
                'background': '#D2E5FF'
            },
            'hover': {
                'border': '#2B7CE9',
                'background': '#D2E5FF'
            }
        }
        node['font'] = {'size': 10}
    
    net.show_buttons(filter_=['physics', 'nodes', 'edges', 'layout'])
    
    # Альтернативное сохранение
    try:
        net.show(output_file)
    except:
        html = net.generate_html()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
    
    print(f"Граф сохранен в файл: {output_file}")

def main():
    data = load_data('faunds.json')
    G = build_graph(data)
    visualize_graph(G)

if __name__ == '__main__':
    main()