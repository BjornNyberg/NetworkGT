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

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import *
from qgis.PyQt.QtGui import QIcon
import os,sys,collections,math,datetime

class Flow2D(QgsProcessingAlgorithm):

    Grid = 'Contour Grid'
    outGrid = 'outGrid'
    xx = 'xx perm'
    xy = 'xy perm'
    yy = 'yy perm'
    Direction = 'Direction'
    steps = 'Steps'
    end = 'End'
    tol = 'tol'
    lowPressure ='LP'
    highPressure = 'HP'
    mu = 'mu'

    def __init__(self):
        super().__init__()

    def name(self):
        return "2D Flow"

    def tr(self, text):
        return QCoreApplication.translate("2D Flow", text)

    def displayName(self):
        return self.tr("2D Flow")

    def group(self):
        return self.tr("5. Flow")

    def shortHelpString(self):
        return self.tr("Solves for 2D flow across a rectangular contour grid with user defined boundary pressure conditions. The user has the option to define the flow direction and pressure conditions between two open boundaries. \n The required input is a topology parameters contour grid with a calculated effective permeability tensor (Kxx, Kxy, Kyy). The output creates a 2D flow contour grid with additional attribute fields including Pressure (Pa), Flow Velocity (m/s) and the Azimuth of the flow direction. \n Additionally the user can simulate the flow of a tracer through the contour grid by defining an end time (s) and a number of time-steps. This will output a Timeseries contour grid containing tracer concentrations (ranging from 0-1) for each time-step. \n N.B. The effective permeability tensor must be given in millidarcy's (mD).\n Please refer to the help button for more information.")

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
            self.Grid,
            self.tr("Contour Grid"),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterField(self.xx,
                                self.tr('xx permeability'), parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(self.xy,
                                self.tr('xy permeability'), parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(self.yy,
                                self.tr('yy permeability'), parentLayerParameterName=self.Grid, type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterEnum(self.Direction,
                        self.tr('Select Flow Direction'), options=[self.tr("left to right"),self.tr("right to left"),self.tr("bottom to top"),self.tr("top to bottom")],defaultValue=0))
        param1 = QgsProcessingParameterNumber(self.steps,
                                self.tr('Number of steps'), QgsProcessingParameterNumber.Integer,1, minValue = 1)
        param2 = QgsProcessingParameterNumber(self.end,
                                self.tr('End Time (seconds)'), QgsProcessingParameterNumber.Double,1.0, minValue = 0.0)
        param3 = QgsProcessingParameterNumber(self.lowPressure,
                                 self.tr('Low Pressure (Pa)'), QgsProcessingParameterNumber.Double,0.0, minValue=0.0)
        param4 = QgsProcessingParameterNumber(self.highPressure,
                                 self.tr('High Pressure (Pa)'), QgsProcessingParameterNumber.Double,1.0, minValue=0.0)
        param5 = QgsProcessingParameterNumber(self.mu,
                              self.tr('Viscosity (Pa.s)'), QgsProcessingParameterNumber.Double,0.001, minValue=0.000001)


        param1.setFlags(param1.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param2.setFlags(param2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param3.setFlags(param3.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param4.setFlags(param4.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param5.setFlags(param5.flags() | QgsProcessingParameterDefinition.FlagAdvanced)


        self.addParameter(param1)
        self.addParameter(param2)
        self.addParameter(param5)
        self.addParameter(param3)
        self.addParameter(param4)


        self.addParameter(QgsProcessingParameterFeatureSink(
            self.outGrid,
            self.tr("2D Flow Grid"),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):
        try:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            sys.path.insert(0,dir_path)
            import porepy as pp
            import numpy as np
            import scipy.sparse as sps
            import flow as f
            from fcts import read_cart_grid, bc_flag, argsort_cart_grid
            from tracer import Tracer
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',''))
            feedback.reportError(QCoreApplication.translate('Error','Please install porepy dependencies'))
            return {}

        #Parameters
        layer = self.parameterAsLayer(parameters, self.Grid, context)
        xx = self.parameterAsString(parameters, self.xx, context)
        xy = self.parameterAsString(parameters, self.xy, context)
        yy = self.parameterAsString(parameters, self.yy, context)
        steps = self.parameterAsInt(parameters, self.steps, context)
        end = self.parameterAsDouble(parameters, self.end, context)  * pp.SECOND
        dV = self.parameterAsInt(parameters, self.Direction, context)
        tol = 1e-4* pp.METER
        lP =  parameters[self.lowPressure] * pp.PASCAL
        hP =  parameters[self.highPressure] * pp.PASCAL
        mu = 1e-3 * pp.PASCAL * pp.SECOND #Define here the dynamic viscosity of the liquid phase in [Pa s]

        if dV == 0:
            direction = "left_to_right"
        elif dV == 1:
            direction = "right_to_left"
        elif dV == 2:
            direction = "bottom_to_top"
        else:
            direction = "top_to_bottom"

        try:
            field_check = layer.fields().indexFromName('Rotation')
            if field_check == -1:
                feedback.reportError(QCoreApplication.translate('Error','Invalid Contour Grid layer - please run the contour grid tool prior to the 2D Flow tool'))
                return {}

        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','No attribute table found. Do not use the "Selected features only" option'))
            return {}

        if lP > hP:
            feedback.reportError(QCoreApplication.translate('Error','Low pressure value is higher than high pressure value.'))
            return {}
        newFields = ['Pressure','Flux','Azimuth','Tracer','StartTime','EndTime']

        fields = QgsFields()
        for field in layer.fields():
            if field.name() not in newFields:
                fields.append(QgsField(field.name(),field.type()))

        for field in newFields[:-2]:
            fields.append(QgsField(field,QVariant.Double))
        fields.append(QgsField('StartTime',QVariant.DateTime))
        fields.append(QgsField('EndTime',QVariant.DateTime))

        (writer, dest_id) = self.parameterAsSink(parameters, self.outGrid, context,
                                                           fields, QgsWkbTypes.Polygon, layer.sourceCrs())

        #Define xx,yy and xy perm
        kxx = []
        kyy = []
        kxy = []

        #Get dictionary of features
        features = {feature['Sample_No_']:feature for feature in layer.selectedFeatures()}
        if len(features) == 0:
            features = {feature['Sample_No_']:feature for feature in layer.getFeatures()}
            extent = layer.extent()
        else:
            extent = layer.boundingBoxOfSelected()
        total = len(features)

        if total == 0:
            feedback.reportError(QCoreApplication.translate('Error','No grid cells found in the input dataset'))
            return {}

        c = 0

        # Sort data by Sample No
        features = collections.OrderedDict(sorted(features.items()))
        W = False
        for FID,feature in features.items():
            c+=1
            if total != -1:
                feedback.setProgress(int(c*total))

            xxV,yyV,xyV = feature[xx],feature[yy],feature[xy]
            if xxV == 0 and yyV == 0 and xyV == 0:
                feedback.reportError(QCoreApplication.translate('Info','Warning: Grid sample no. %s contains a pereambility of 0 for XX, XY and YY' %(FID)))
                W = True

            kxx.append(xxV*pp.MILLIDARCY)
            kyy.append(yyV*pp.MILLIDARCY)
            kxy.append(xyV*pp.MILLIDARCY)

            if type(xxV) != float or type(xyV) != float or type(yyV) != float:
                feedback.reportError(QCoreApplication.translate('Info','Warning: Grid sample no. %s contains non-float values for pereambility measurements' %(FID)))
                W = True
        if W:
            feedback.reportError(QCoreApplication.translate('Info','Invalid permeability measurements created an empty 2D flow grid!'))
            return {}

        kxx,kyy,kxy = np.array(kxx),np.array(kyy),np.array(kxy)

        rotation = feature['Rotation']
        spacing = feature['Spacing']

        P = 10 #Precision
        #Read grid geometry

        extentGeom = QgsGeometry.fromRect(extent)
        extentGeom = extentGeom.orientedMinimumBoundingBox()

        dWidth = round(extentGeom[4],P)
        dHeight = round(extentGeom[3],P) #Domain width and height

        Ny = round(dHeight / spacing)
        Nx = round(dWidth / spacing)

        count = Nx*Ny
        if count != c:
            feedback.reportError(QCoreApplication.translate('Warning','Warning: Selected contour grid does not appear to be a rectangle.'))
            feedback.reportError(QCoreApplication.translate('Warning',''))

        # Read the grid
        gb = read_cart_grid(Nx,Ny,dWidth,dHeight)

        feedback.pushInfo(QCoreApplication.translate('Output', 'Constructing grid with %s columns and %s rows a domain size (width x height) of %s x %s.' % (Nx,Ny,dWidth,dHeight)))

        # mask that map the permeability from qgis to pp, and vice-versa
        mask, inv_mask = argsort_cart_grid(Nx, Ny)

        param_flow = {"tol": tol,
                  "kxx": kxx[mask] / mu,
                  "kyy": kyy[mask] / mu,
                  "kxy": kxy[mask] / mu,

                  "flow_direction": direction,
                  "low_value": lP,
                  "high_value": hP,

                  "north": np.array([0, 1, 0]),
                  }
        try:
            flow = f.Flow(gb)
            flow.set_data(param_flow, bc_flag)
            flow.solve()
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error',str(e)))
            return {}

        if steps > 1:
            param_tracer = {"tol": tol,
                    "num_steps": steps,
                    "end_time": end,

                    "flow_direction": direction,
                    "low_value": lP,
                    "high_value": hP}

            tracer = Tracer(gb)
            tracer.set_data(param_tracer, bc_flag)
            tracer.solve()

        t = []
        for g, d in gb:
            p = d[pp.STATE][flow.pressure]
            v = d[pp.STATE][flow.norm_flux]
            a = d[pp.STATE][flow.azimuth]
            if steps > 1:
                for time_step, current_time in enumerate(tracer.all_time):
                    var_name = tracer.variable + "_" + str(time_step)
                    traceD = d[pp.STATE][var_name]
                    traceD = traceD[inv_mask]
                    t.append(traceD)

        #Reshape the output data
        p = p[inv_mask]
        v = v[inv_mask]
        a = a[inv_mask]

        feedback.pushInfo(QCoreApplication.translate('Output','Updating Feature Layer'))

        #Update the dataset
        fet = QgsFeature()
        for enum,FID in enumerate(features):
            feature = features[FID]
            FID = feature.id()
            geom = feature.geometry()
            if total != -1:
                feedback.setProgress(int(enum*total))

            rows = []
            for field in layer.fields():
                if field.name() not in newFields:
                    rows.append(feature[field.name()])

            aV = math.degrees(float(a[enum]))+ rotation
            if type(aV) == float:
                aV %= 360
            if dV < 2:
                if aV < 180:
                    aV += 180
                else:
                    aV -= 180

            rows.extend([round(float(p[enum]),P),round(float(v[enum]),P),round(float(aV),2)])

            if steps > 1:

                time = datetime.datetime(1, 1, 1, 0, 0, 0)
                deltaTime = datetime.timedelta(seconds=end/steps)

                for n in range(len(t)):
                    newRows = rows.copy()
                    newRows.append(round(float(t[n][enum]),P))
                    newRows.append(str(time))
                    time += deltaTime
                    newRows.append(str(time))

                    fet.setGeometry(geom)
                    fet.setAttributes(newRows)
                    writer.addFeature(fet,QgsFeatureSink.FastInsert)
            else:
                fet.setGeometry(geom)
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

        return {self.outGrid:dest_id}
