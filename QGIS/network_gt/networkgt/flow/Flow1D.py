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

import datetime,sys,os,tempfile,string,random,csv, math
import processing as st
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class Flow1D(QgsProcessingAlgorithm):

    Network = 'Fracture Network'
    outLine = '1D Flow'
    Direction = 'Direction'
    boundSize = 'mesh size'
    tol = 'Tolerance'
    steps = 'Steps'
    end = 'End'
    lowPressure ='LP'
    highPressure = 'HP'
    mu = 'mu'

    def __init__(self):
        super().__init__()

    def name(self):
        return "1D Flow"

    def tr(self, text):
        return QCoreApplication.translate("1D Flow", text)

    def displayName(self):
        return self.tr("1D Flow")

    def group(self):
        return self.tr("5. Flow")

    def shortHelpString(self):
        return self.tr("Solves for 1D flow across a fracture network with user defined boundary pressure conditions. The user has the option to define the flow direction and pressure conditions between two open boundaries. \n The required input is a fracture network linestring with calculated fracture transmissivities (mD.m). The output creates a 1D flow linestring of the fracture network with additional attribute fields including Pressure (Pa), Flow Velocity (m/s) and the Azimuth of the flow direction.  \n Additionally the user can simulate the flow of a tracer through the fracture network by defining an end time (s) and a number of time-steps. This will output a Timeseries linestring containing tracer concentrations (ranging from 0-1) for each time-step. \n N.B. The larger the fracture network the more computational time the simulation takes. It is, therefore, recommended that the user applies the Simplify Network tool to help reduce computational time.\n Please refer to the help button for more information.")

    def groupId(self):
        return "5. Flow"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/5.-Flow-Assessment"

    def createInstance(self):
        return type(self)()

##    def icon(self):
##        n,path = 2,os.path.dirname(__file__)
##        while(n):
##            path=os.path.dirname(path)
##            n -=1
##        pluginPath = os.path.join(path,'icons')
##        return QIcon( os.path.join( pluginPath, 'CG.jpg') )

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterEnum(self.Direction,
                                self.tr('Select Flow Direction'), options=[self.tr("left to right"),self.tr("right to left"),self.tr("bottom to top"),self.tr("top to bottom")],defaultValue=0))

        param1 = QgsProcessingParameterNumber(self.steps,
                                self.tr('Number of steps'), QgsProcessingParameterNumber.Integer,1, minValue = 1)
        param2 = QgsProcessingParameterNumber(self.end,
                                self.tr('End Time (seconds)'), QgsProcessingParameterNumber.Double,1.0,  minValue=0.0)
        param3 = QgsProcessingParameterNumber(self.mu,
                                 self.tr('Viscosity (Pa.s)'), QgsProcessingParameterNumber.Double,0.001, minValue=0.000001)
        param4 = QgsProcessingParameterNumber(self.boundSize,
                                self.tr('Mesh Size (m)'), QgsProcessingParameterNumber.Double,100.0, minValue = 0.000001)
        param5 = QgsProcessingParameterNumber(self.lowPressure,
                                 self.tr('Low Pressure (Pa)'), QgsProcessingParameterNumber.Double,0.0, minValue=0.0)
        param6 = QgsProcessingParameterNumber(self.highPressure,
                                 self.tr('High Pressure (Pa)'), QgsProcessingParameterNumber.Double,1.0, minValue=0.000001)

        param1.setFlags(param1.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param2.setFlags(param2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param3.setFlags(param3.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param4.setFlags(param4.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param5.setFlags(param5.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param6.setFlags(param6.flags() | QgsProcessingParameterDefinition.FlagAdvanced)

        self.addParameter(param1)
        self.addParameter(param2)
        self.addParameter(param3)
        self.addParameter(param5)
        self.addParameter(param6)
        self.addParameter(param4)

        self.addParameter(QgsProcessingParameterFeatureSink(
                    self.outLine,
                    self.tr("1D Flow"),
                    QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):
        try:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            sys.path.insert(0,dir_path)
            import porepy as pp
            from flow import Flow_Model1
            from tracer import Tracer
            from fcts import read_network, bc_flag
            from math import ceil
            import numpy as np
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',''))
            feedback.reportError(QCoreApplication.translate('Error','Please install porepy dependencies'))
            return {}

        #Parameters
        layer = self.parameterAsLayer(parameters, self.Network, context)
        h = self.parameterAsDouble(parameters, self.boundSize, context) * pp.METER
        steps = self.parameterAsInt(parameters, self.steps, context)
        endv = self.parameterAsInt(parameters, self.end, context) * pp.SECOND
        tol = 1e-8 * pp.METER
        d = self.parameterAsInt(parameters, self.Direction, context)
        lP =  parameters[self.lowPressure] * pp.PASCAL
        hP =  parameters[self.highPressure] * pp.PASCAL
        mu = parameters[self.mu] * pp.PASCAL * pp.SECOND

        if d == 0:
            direction = "left_to_right"
        elif d == 1:
            direction = "right_to_left"
        elif d == 2:
            direction = "bottom_to_top"
        else:
            direction = "top_to_bottom"

        if lP > hP:
            feedback.reportError(QCoreApplication.translate('Error','Low pressure value is higher than high pressure value.'))
            return {}

        params  = {'INPUT':layer,'OUTPUT':'memory:'}
        explode = st.run("native:explodelines",params,context=context,feedback=feedback)

        layer2 = explode['OUTPUT']

        #Create new field to fracture line
        newFields = ['ID','Pressure','Flux','Azimuth','Tracer','StartTime','EndTime']

        if layer.fields().indexFromName('Transmisiv') == -1:
            feedback.reportError(QCoreApplication.translate('Error','Please calculate the transmissivity using the Aperture tool or define a new transmissivity field labelled "Transmisiv" in mD.m'))
            return {}

        fields = QgsFields()

        for field in layer.fields():
            if field.name() not in newFields:
                fields.append(QgsField(field.name(),field.type()))

        for field in newFields[:-2]:
            fields.append(QgsField(field,QVariant.Double))
        fields.append(QgsField('StartTime',QVariant.DateTime))
        fields.append(QgsField('EndTime',QVariant.DateTime))

        (writer, dest_id) = self.parameterAsSink(parameters, self.outLine, context,
                                                           fields, QgsWkbTypes.LineString, layer.sourceCrs())

        #Define fracture geometries
        outDir = os.path.join(tempfile.gettempdir(),'PorePy')
        if not os.path.exists(outDir):
            os.mkdir(outDir)
        fname = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
        outName = os.path.join(outDir,'%s.txt'%(fname))

        k, l = {}, {} #k is the pereambility in m2, l is the fracture length in m
        data = {}

        P = 1000000 #Tolerance for the point precision

        feedback.pushInfo(QCoreApplication.translate('Info','Reading Fracture Network'))
        field_check = layer2.fields().indexFromName('origLen')
        if field_check != -1:
            feedback.reportError(QCoreApplication.translate('Info','Warning: Applying the origLen field to calculate fracture length'))
        W = False
        with open(outName, 'w') as f:
            f.write('ID,startx,starty,endx,endy')
            f.write('\n')
            for enum,feature in enumerate(layer2.getFeatures()):
                try:
                    geom = feature.geometry().asPolyline()
                except Exception:
                    geom = feature.geometry().asMultiPolyline()[0]
                start,end = geom[0],geom[-1]

                startx,endx = ceil(start.x()*P)/P,ceil(end.x()*P)/P
                starty,endy = ceil(start.y()*P)/P,ceil(end.y()*P)/P

                t = feature['Transmisiv']
                if t == 0:
                    W = True

                if field_check != -1:
                    lValue = feature['origLen']
                    if type(lValue) != float:
                        feedback.reportError(QCoreApplication.translate('Info','Warning: origLen field contains non-float values'))
                        return {}
                    l[feature.id()] = lValue / feature.geometry().length()
                else:
                    l[feature.id()] = feature.geometry().length()

                if type(t) != float:
                    feedback.reportError(QCoreApplication.translate('Info','Warning: Transmisivity field contains non-float values'))
                    return {}

                k[feature.id()] = t * pp.MILLIDARCY * pp.METER

                row = '%s,%s,%s,%s,%s'%(feature.id(),startx,starty,endx,endy)
                f.write(row) #ID,startx,starty,endx,endy
                f.write('\n')

                rows = []
                for field in layer.fields():
                    if field.name() not in newFields:
                        rows.append(feature[field.name()])
                data[feature.id()] = rows

        if len(data) == 0:
            feedback.reportError(QCoreApplication.translate('Info','No fractures found in the input dataset'))
            return {}
        elif enum > 2000:
            feedback.reportError(QCoreApplication.translate('Info','Warning - Fracture network exceeds 2000 branches. To improve performance consider subsampling and/or simplifying the Fracture Network using the "Simplify Network" tool.'))

        if W:
            feedback.reportError(QCoreApplication.translate('Info','Warning - Transmisivity value(s) of 0 in the fracture network will not produce flow'))


        network, mask, pts_shift = read_network(outName, tol=tol)

        mesh_args = {"mesh_size_frac": h, "mesh_size_bound": h,'file_name':outDir}

        feedback.pushInfo(QCoreApplication.translate('Info','Creating Mesh from %s'%(network)))

        try:
            gb = network.mesh(mesh_args, dfn=True, tol=tol,)
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Info',str(e)))
            feedback.reportError(QCoreApplication.translate('Info',''))
            feedback.reportError(QCoreApplication.translate('Info','Failure creating the fracture network mesh. Please check that NetworkGT was properly configured to use gmsh meshing according to the installation guidelines'))
        flow = Flow_Model1(gb)

        param_flow = {"tol": tol,
                          "k": np.array([k[m] for m in mask])/mu,
                          "length_ratio": np.array([l[m] for m in mask]),
                          "flow_direction": direction,
                          "low_value": lP,
                          "high_value": hP,
                          "north": np.array([0, 1, 0])}

        param_tracer = {"tol": tol,
                  "num_steps": steps,
                  "end_time": endv,

                  "flow_direction": direction,
                  "low_value": lP,
                  "high_value": hP}

        flow.set_data(param_flow, bc_flag)

        feedback.pushInfo(QCoreApplication.translate('Info','Solving Fluid Flow'))
        flow.solve()

        # get the results for qgis
        if steps > 1:
            feedback.pushInfo(QCoreApplication.translate('Info','Solving Tracer'))
            tracer = Tracer(gb)
            tracer.set_data(param_tracer, bc_flag)
            tracer.solve()

        feedback.pushInfo(QCoreApplication.translate('Info','Creating Feature Layer'))
        fet = QgsFeature()
        for g, d in gb:
            # avoid to consider the 0d grids
            if g.dim == 0:
                continue

            # get the data for the current grid
            p = d[pp.STATE][flow.pressure]
            norm_flux = d[pp.STATE][flow.norm_flux]
            azimuth = d[pp.STATE][flow.azimuth]

            # get the cell to nodes map
            cell_nodes = g.cell_nodes()
            indptr = cell_nodes.indptr
            indices = cell_nodes.indices

            # all the data that need to be exported are given as cell_SOMETHING
            for c in np.arange(g.num_cells):
                nodes_loc = indices[indptr[c]:indptr[c+1]]
                # each column gives a node for the segment
                # NOTE: the nodes are translated compared to the original network
                pnt = g.nodes[:2, nodes_loc] + pts_shift
                # value of the computed fields
                cell_pressure = p[c]
                # flux norm
                cell_norm_flux = norm_flux[c]
                # the fracture id and data
                cell_frac_id = mask[g.frac_num]
                rows = data[cell_frac_id].copy()
                # value of the azimuth
                # NOTE: velocity zero gives nan as azimuth angle
                cell_azimuth = math.degrees(azimuth[c])

                if cell_norm_flux == 0:
                    rows.extend([float(cell_frac_id),float(cell_pressure),float(cell_norm_flux),NULL])
                else:
                    #cell_azimuth %= 360
                    rows.extend([float(cell_frac_id),float(cell_pressure),float(cell_norm_flux),float(cell_azimuth)])

                points = [QgsPointXY(pnt[0][0],pnt[1][0]),QgsPointXY(pnt[0][1],pnt[1][1])]
                geom = QgsGeometry.fromPolylineXY(points)
                fet.setGeometry(geom)

                if steps > 1:

                    time = datetime.datetime(1, 1, 1, 0, 0, 0)
                    deltaTime = datetime.timedelta(seconds=endv/steps)

                    for time_step, current_time in enumerate(tracer.all_time):
                        var_name = tracer.variable + "_" + str(time_step)
                        tr = d[pp.STATE][var_name]
                        cell_tracer = tr[c]
                        
                        newRows = rows.copy()
                        newRows.append(float(round(cell_tracer,6)))
                        newRows.append(str(time))
                        time += deltaTime
                        newRows.append(str(time))

                        fet.setAttributes(newRows)
                        writer.addFeature(fet,QgsFeatureSink.FastInsert)
                else:
                    fet.setAttributes(rows)
                    writer.addFeature(fet,QgsFeatureSink.FastInsert)

        try:
            os.remove(outName) #Delete temp csv file
        except Exception:
            pass

        return {self.outLine:dest_id}
