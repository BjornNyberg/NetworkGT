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

import  os,csv,subprocess,tempfile

arcpy.env.overwriteOutput = True

def main (nodes,branch,infc3,output,output2,units):

    try:

	if 'shp' in output2:
	    arcpy.AddError('Output parameter must be saved in a geodatabase')
	    sys.exit()

     	curfields = [f.name for f in arcpy.ListFields(nodes)]
        if 'Sample_No_' not in curfields:
            arcpy.AddError("Nodes input is invalid - Run Branches and Nodes tool prior to Topology Parameters tool")
            sys.exit()
        arcpy.AddMessage('Reading input files')
     	curfields = [f.name for f in arcpy.ListFields(branch)]
        if 'Sample_No_' not in curfields:
            arcpy.AddError("Branches input is invalid - Run Branches and Nodes tool prior to Topology Parameters tool")
            sys.exit()

        outDir = os.path.join(tempfile.gettempdir(),'NetworkGT')
        if not os.path.exists(outDir):
            os.mkdir(outDir)

        fname = os.path.join(os.path.dirname(os.path.realpath(__file__)),'csv2xlsx.py')
        temp_csv1 = os.path.join(outDir,'temp_csv1.csv')  #Create temp csv files to handle geodatabase files
        temp_csv2 = os.path.join(outDir,'temp_csv2.csv')
        temp_csv3 = os.path.join(outDir,'temp_csv3.csv')

        python_executer = r"C:\Python27\ArcGISx6410.6\python.exe"

        curfields = curfields = [f.name for f in arcpy.ListFields(infc3)]

        if 'Area' and 'Circumfere' and 'S_Radius' in curfields:
            fields = ['Circumfere','Area','S_Radius','OID@']
            check = True

        else:
            fields = ['SHAPE@','OID@']

        with open(temp_csv3,'w') as f:
            with arcpy.da.SearchCursor(infc3,fields) as cursor:
                for row in cursor:

                    if len(fields) == 2:
                        circ = row[0].getLength('PLANAR',units)
                        area = row[0].getArea('PLANAR',units)
                        f.write('%s:%s:%s\n'%(row[1],circ,area))

                    else:
                        circ = row[0]
                        area = row[1]
                        f.write('%s:%s:%s\n'%(row[3],circ,area))

                        if check:
                            s_units = row[2].split(' ')[1]
                            if s_units != units:
                                arcpy.AddWarning('Sample Area search radius units in %s do not match the selected units of %s'%(s_units,units))
                                arcpy.AddWarning('Changing units to %s to match Sample Area search radius units'%(s_units))
                                units = s_units

                            check = False

	m = 0

        with open(temp_csv1,'w') as f:
            with arcpy.da.SearchCursor(nodes,['Sample_No_','Class']) as cursor:
                for row in cursor:
                    f.write('%s:%s\n'%(row[0],row[1]))

        with open(temp_csv2,'w') as f:
            with arcpy.da.SearchCursor(branch,['Sample_No_','B_Weight','Connection','SHAPE@']) as cursor:
                for row in cursor:
                    Length = row[3].getLength('PLANAR',units)

                    f.write('%s:%s:%s:%s\n'%(row[0],row[1],row[2],Length))

	if not output:
	    output = os.path.join(os.path.dirname(os.path.realpath(__file__)),'temp_table.xls')
	    delete = True
	else:
	    delete = False

        expression = [python_executer,fname,temp_csv1,temp_csv2,temp_csv3,output]
        arcpy.AddMessage('Calculating parameters')
        try:
            subprocess.check_output(expression,shell=True,stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as e:
            raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

        arcpy.AddMessage('Creating output files')
        template = os.path.join(os.path.split(os.path.dirname(os.path.realpath(__file__)))[0],'Symbology Layers\Templates.gdb','Topology_Template')
        arcpy.CreateFeatureclass_management(os.path.dirname(output2),os.path.basename(output2),"",template,"ENABLED","ENABLED",infc3)
        infc3_fields = [f.name for f in arcpy.ListFields(infc3)]

        if 'S_Radius' in infc3_fields:
            t_fields = ["SHAPE@",'Sample_No_','S_Radius']
            in_fields = ['SHAPE@','OID@','S_Radius']
            arcpy.AddField_management(output2, 'S_Radius',"TEXT")
        else:
            t_fields = ["SHAPE@",'Sample_No_']
            in_fields = ['SHAPE@','OID@']


        with arcpy.da.InsertCursor(output2,t_fields) as cursor2:
            with arcpy.da.SearchCursor(infc3,in_fields) as cursor:
                for feature in cursor:
                    if len(in_fields) == 3:
                        data = [feature[0],feature[1],feature[2]]
                    else:
                        data = [feature[0],feature[1]]

                    cursor2.insertRow(data)

	del cursor,cursor2,feature,t_fields,in_fields


        arcpy.env.workspace = os.path.dirname(output)

        table = os.path.join(arcpy.env.workspace,"temp.dbf")


        arcpy.ExcelToTable_conversion(os.path.basename(output),os.path.basename(table), "Data")

        curfields2 =  [f.name for f in arcpy.ListFields(table)]
        fields = curfields2[1:]

        index = fields.index("Sample_No_")
        data = {}
        arcpy.AddMessage('Gathering Data')
        with arcpy.da.SearchCursor(table,fields) as cursor:
            for row in cursor:
                values = {}
                for enum,field in enumerate(fields):
                    values[field] = row[enum]
                data[row[index]] = values

        fields.append('OID@')
        arcpy.AddMessage('Updating Feature Class')
        with arcpy.da.UpdateCursor(output2,fields) as cursor:
            for row in cursor:
                try:
                    if row[-1] in data:
                        for enum,field in enumerate(fields[:-1]):
                            row[enum] = data[row[-1]-m][field]
                        cursor.updateRow(row)
                    else:
                        cursor.deleteRow()

                except Exception,e:
                    arcpy.AddMessage(e)
                    continue

        os.remove(table)
        os.remove(table[:-3] + 'cpg')
        os.remove(table + '.xml')

	if delete:
	    os.remove(output)

    except Exception,e:
        arcpy.AddError('%s'%(e))



if __name__ == "__main__":
    ###Inputs###


    infc = arcpy.GetParameterAsText(0)
    infc2 = arcpy.GetParameterAsText(1)
    infc3 = arcpy.GetParameterAsText(2)
    units = arcpy.GetParameterAsText(3)
    output = arcpy.GetParameterAsText(4)
    output2 = arcpy.GetParameterAsText(5)


    main(infc,infc2,infc3,output,output2,units)
