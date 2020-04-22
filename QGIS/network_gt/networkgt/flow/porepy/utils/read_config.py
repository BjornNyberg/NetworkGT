import multiprocessing,os,tempfile
def read():
    outDir = os.path.join(tempfile.gettempdir(),'porepy')
    config_file = os.path.join(outDir,'config_file.txt')
    f =  open(config_file,'r')
    config = {'gmsh_path': r'%s'%(f.read()),
          'num_processors': multiprocessing.cpu_count() }
    f.close()
    return config
