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

import os, subprocess, tempfile
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingAlgorithm
from qgis.utils import iface
from PyQt5.QtWidgets import QMessageBox, QFileDialog


class configureNetworkGT(QgsProcessingAlgorithm):

    def __init__(self):
        super().__init__()

    def name(self):
        return "Configure"

    def tr(self, text):
        return QCoreApplication.translate("Configure NetworkGT", text)

    def displayName(self):
        return self.tr("Configure NetworkGT")

    def group(self):
        return self.tr("Configure")

    def shortHelpString(self):
        return self.tr("Install the necessary dependencies required for NetworkGT. WARNING: This may break the dependencies of other plugins and/or python modules")

    def groupId(self):
        return "Configure"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/Installation"

    def createInstance(self):
        return type(self)()
    def initAlgorithm(self, config=None):
        pass
   # self.addParameter(QgsProcessingParameterBoolean(self.Export, self.tr("Export SVG File"),False))

    def processAlgorithm(self, parameters, context, feedback):

        reply = QMessageBox.question(iface.mainWindow(), 'Install NetworkGT Dependencies',
                 'WARNING: Installing dependencies for NetworkGT may break the dependencies of other plugins and/or python modules. Do you wish to continue?', QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                is_admin = os.getuid() == 0
            except AttributeError:
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

            modules = ['cython','networkx','scipy','scikit-image','sympy']
            moduleVersions = ['pip','pandas==0.25.1','plotly==3.3.0','meshio == 2.3.8']

            if not is_admin:
                feedback.reportError(QCoreApplication.translate('Warning','Attempting to install necessary python modules without admin access.'))

            for module in moduleVersions:
                try:
                    if is_admin:
                        status = subprocess.check_call(['python3','-m', 'pip', 'install', module, '--upgrade'])
                    else:
                        status = subprocess.check_call(['python3','-m', 'pip', 'install', module, '--upgrade','--user'])
                except Exception:
                    feedback.reportError(QCoreApplication.translate('Warning','Failed to install %s - consider installing manually'%(module)))
                    continue

            for module in modules:
                try:
                    if is_admin:
                        status = subprocess.check_call(['python3','-m', 'pip', 'install', module])
                    else:
                        status = subprocess.check_call(['python3','-m', 'pip', 'install', module,'--user'])

                    if status != 0:
                        feedback.reportError(QCoreApplication.translate('Warning','Failed to install %s - consider installing manually'%(module)))
                except Exception:
                    feedback.reportError(QCoreApplication.translate('Warning','Failed to install %s - consider installing manually'%(module)))
                    continue

        reply = QMessageBox.question(iface.mainWindow(), 'Install NetworkGT Dependencies',
                 'Do you want to configure gmsh?', QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:

            fname,_ = QFileDialog.getOpenFileName(iface.mainWindow(),"Select Gmsh program", ""," All Files (*.*);; exe (*.exe);; app (*.app)")
            if os.path.exists(fname):
                if fname.endswith('.app'):
                    fname = os.path.join(fname,'contents/MacOS/gmsh')
                if 'gmsh' not in fname:
                    feedback.reportError(QCoreApplication.translate('Warning','Please download the Gmsh program at http://gmsh.info/ or visit the NetworkGT website for more help at https://github.com/BjornNyberg/NetworkGT/wiki/Installation'))
                    return {}

                outDir = os.path.join(tempfile.gettempdir(),'PorePy')
                if not os.path.exists(outDir):
                    os.mkdir(outDir)
                config_file = os.path.join(outDir,'config_file.txt')
                with open(config_file, "w") as f:
                    f.write(str(fname))
            else:
                feedback.reportError(QCoreApplication.translate('Warning','Please download the Gmsh program at http://gmsh.info/ or visit the NetworkGT website for more help at https://github.com/BjornNyberg/NetworkGT/wiki/Installation'))
        return {}
