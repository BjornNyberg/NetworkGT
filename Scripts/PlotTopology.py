#==================================
#Author Bjorn Burr Nyberg 
#University of Bergen
#Contact bjorn.nyberg@uib.no
#Copyright 2016
#==================================

'''This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.'''

import  os,arcpy, subprocess

def main (shp):
    curfields = set([f.name for f in arcpy.ListFields(shp)])
    fields = set(['I','Y','X','No__Branch'])
    check = fields - curfields
    if len(check) != 0:
        arcpy.AddError("Feature layer attributes not valid - run Topology Parameters tool")
    	sys.exit()

    fname = os.path.join(os.path.dirname(os.path.realpath(__file__)),'plottopologydata.py')
    table = os.path.join(os.path.dirname(os.path.realpath(__file__)),'topology_table.xls')
    python_executer = r"C:\Python27\ArcGISx6410.6\pythonw.exe"

    arcpy.env.workspace = os.path.dirname(table)


    arcpy.TableToExcel_conversion(shp,os.path.basename(table))

    expression = [python_executer,fname,table]
    DETACHED_PROCESS = 0x00000008
    P=subprocess.Popen(expression, shell=False, stdin=None, stdout=None, stderr=None, close_fds=True,creationflags=DETACHED_PROCESS)

if __name__ == "__main__":        
    ###Inputs###
        
    shp = arcpy.GetParameterAsText(0)

    main(shp)
