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


import  os,arcpy,subprocess,tempfile

def main (infc,fields,groupby):

    outDir = os.path.join(tempfile.gettempdir(),'NetworkGT')
    if not os.path.exists(outDir):
        os.mkdir(outDir)

    fname = os.path.join(os.path.dirname(os.path.realpath(__file__)),'DistributionPlotData.py')
    temp_csv = os.path.join(outDir,'temp_csv.csv')
    python_executer = r"C:\Python27\ArcGISx6410.6\python.exe"


    if groupby:
    	fields.append(groupby)

    with open(temp_csv,'w') as f:
        with arcpy.da.SearchCursor(infc,fields) as cursor:
            for row in cursor:
                if groupby:
                    ID = row[1]
                else:
                    ID = 0
                f.write('%s:%s\n'%(row[0],ID))

    expression = [python_executer,fname,temp_csv]
    DETACHED_PROCESS = 0x00000008
    P=subprocess.Popen(expression, shell=False, stdin=None, stdout=None, stderr=None, close_fds=True,creationflags=DETACHED_PROCESS)

if __name__ == "__main__":
    ###Inputs###

    infc = arcpy.GetParameterAsText(0)
    field = [arcpy.GetParameterAsText(1)]
    grp = arcpy.GetParameterAsText(2)

    main(infc,field,grp)
