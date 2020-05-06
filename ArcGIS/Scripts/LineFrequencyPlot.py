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


import  os,arcpy, subprocess,sys,tempfile

def main (infc,field,fields):

    fname = os.path.join(os.path.dirname(os.path.realpath(__file__)),'LineFrequencyPlotData.py')
    outDir = os.path.join(tempfile.gettempdir(),'NetworkGT')
    if not os.path.exists(outDir):
        os.mkdir(outDir)
    temp_csv = os.path.join(outDir,'temp_csv.csv')
    python_executer = r"C:\Python27\ArcGISx6410.6\python.exe"

    if not fields:
        fields = []
    else:
        fields = [fields]

    curfields = [f.name for f in arcpy.ListFields(infc)]

    if 'Distance' not in curfields or 'Sample_No_' not in curfields:
        arcpy.AddError("Run Line Sampling tool prior to plotting")
        sys.exit()

    fields.extend(['Distance','Sample_No_'])

    fields.append(field)


    with open(temp_csv,'w') as f:
        with arcpy.da.SearchCursor(infc,fields) as cursor:
            for row in cursor:

                if len(fields) == 3:
                    f.write('%s:%s:%s:%s\n'%(row[1],'Total',row[0],row[2]))
                else:
                    f.write('%s:%s:%s:%s\n'%(row[2],row[0],row[1],row[3]))

	del cursor,row

    expression = [python_executer,fname,temp_csv]
    #expression = '%s %s %s' %(python_executer,fname,temp_csv)
    DETACHED_PROCESS = 0x00000008
    P=subprocess.Popen(expression, shell=False, stdin=None, stdout=None, stderr=None, close_fds=True,creationflags=DETACHED_PROCESS)
    #os.system(expression)
if __name__ == "__main__":
    ###Inputs###

    infc = arcpy.GetParameterAsText(0)
    field = arcpy.GetParameterAsText(1)
    fields = arcpy.GetParameterAsText(2)

    main(infc,field,fields)
