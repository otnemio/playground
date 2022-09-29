import os,yaml

def readConfig(key):
    _ROOT = os.path.abspath(os.path.dirname(__file__))
    config_file = os.path.join(_ROOT, "", "config.yaml")
    if os.path.exists(config_file):
        with open(config_file, 'r') as c_file:
            c_data = yaml.load(c_file,Loader=yaml.SafeLoader)
            return c_data[key]
    else:
        return None