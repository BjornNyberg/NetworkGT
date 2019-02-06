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


import  os,arcpy,math,csv
import subprocess
def main (infc,bins,field,grp):
    
    fname = os.path.join(os.path.dirname(os.path.realpath(__file__)),'WeightedRosePlotData.py')
    temp_csv = os.path.join(os.path.dirname(os.path.realpath(__file__)),'temp__wr.csv') 
    python_executer = r"C:\Python27\ArcGISx6410.6\python.exe"
	
    data = {}

    if grp:
	if field:
	    fields = ['SHAPE@',field,grp]
	else:
	    fields = ['SHAPE@','OID@',grp]

    else:
	if field:
	    fields = ['SHAPE@',field]
	else:
	    fields = ['SHAPE@']
    with arcpy.da.SearchCursor(infc,fields) as cursor:
        for row in cursor:

            if field:
                d = row[1]
            else:
                d = 1

            sx,sy = row[0].firstPoint.X,row[0].firstPoint.Y
            ex,ey = row[0].lastPoint.X,row[0].lastPoint.Y

            dx = ex - sx

            dy =  ey - sy

            angle = math.degrees(math.atan2(dy,dx))

            Bearing = (90.0 - angle) % 360

            if grp: 
                ID = row[2]    
            else:
                ID = 1

            if ID in data:
                data[ID].append((Bearing,d))
            else:
                data[ID] = [(Bearing,d)]
            

    with open(temp_csv,'w') as f:
        for k,v in data.iteritems():
            f.write('%s:%s\n'%(k,v))
    del data

    expression = [python_executer,fname,temp_csv,bins]
    DETACHED_PROCESS = 0x00000008
    P=subprocess.Popen(expression, shell=False, stdin=None, stdout=None, stderr=None, close_fds=True,creationflags=DETACHED_PROCESS)
    

if __name__ == "__main__":        
    ###Inputs###
        
    infc = arcpy.GetParameterAsText(0)
    bins = arcpy.GetParameterAsText(1)
    field = arcpy.GetParameterAsText(2)
    grp = arcpy.GetParameterAsText(3)

    main(infc,bins,field,grp)

