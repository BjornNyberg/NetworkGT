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

import sys,time
import os,numpy,time
import pandas as pd

def main(inFC,inFC2,inFC3,output):
    try:

        df = pd.read_csv(inFC,header=None,sep=':')

        df.rename(columns={0:'Sample No.',1:'Class'},inplace=True)

        df['Nodes'] = 0

        df = df[['Sample No.','Class','Nodes']].groupby(['Sample No.','Class']).count().unstack(level=1)

        df.fillna(0,inplace=True)
        df.columns = df.columns.droplevel()

        node_columns = ['I','X','Y','E', 'U']

        for column in node_columns:
            if column not in df:
                df[column] = 0.0

        if 'Error' in df:
            del df['Error']

        df['No. Nodes'] = df.X + df.Y + df.I
        df['No. Branches'] = ((df.X*4.0) + (df.Y*3.0) + df.I)/2.0
        df['No. Lines'] = (df.Y + df.I)/2
        df['No. Connections'] = df.X + df.Y
        df['Connect/Line'] = (2.0*(df.X+df.Y))/df['No. Lines']

        df2 = pd.read_csv(inFC2,header=None,sep=':')
        df2.rename(columns={0:'Sample No.',1:'Branches',2:'Connection',3:'Length'},inplace=True)

        df3 = df2[['Sample No.','Branches','Connection']].groupby(['Sample No.','Connection']).sum().unstack(level=1)

        df3.fillna(0.0,inplace=True)

        df3.columns = df3.columns.droplevel()

        branch_columns = ['C - C','C - I', 'C - U','I - I','I - U','U - U']
        delete_columns = ['C - Error','Error - Error','Error - I', 'Error - U']

        for column in branch_columns:
            if column not in df3:
                df3[column] = 0.0

        for column in delete_columns:
            if column in df3:
                del df3[column]

        df3['No. Branches'] = df3['C - C'] + df3['C - I'] + df3['I - I'] + df3['C - U'] + df3['I - U'] + df3['U - U']

        df2 = df2[['Sample No.','Length','Connection']].groupby(['Sample No.','Connection']).sum().unstack(level=1)
        df2.fillna(0.0,inplace=True)
        df2.columns = df2.columns.droplevel()

        for column in branch_columns:
            if column not in df2:
                df2[column] = 0.0

        for column in delete_columns:
            if column in df2:
                del df2[column]

        df2['Total Trace Length'] = df2['C - C'] + df2['C - I'] + df2['I - I'] + df2['C - U'] + df2['I - U'] + df2['U - U']

        df4=pd.read_csv(inFC3,header=None,sep=':',index_col=0)
        df4.rename(columns={1:'Circumference',2:'Area'},inplace=True)
        df4.index.rename('Sample No.', inplace=True)

        df['Average Line Length'] = df2['Total Trace Length'] / df['No. Lines']
        df['Average Branch Length'] = df2['Total Trace Length'] / df['No. Branches']
        df['Connect/Branch'] = ((3.0*df.Y) + (4.0*df.X)) / df['No. Branches']
        df['Branch Freq'] = df['No. Branches'] / df4['Area']
        df['Line Freq'] = df['No. Lines'] / df4['Area']
        df['NcFreq'] = df['No. Connections'] / df4['Area']
        samples = df.index.tolist()
        df4 = df4.ix[samples]

        time.sleep(10)
        r = df4['Circumference']/(numpy.pi*2.0)

        a = numpy.pi*r*r
        a = df4['Area'] - a
        df['a'] = numpy.fabs(a.round(4))

        df['1D Intensity'] = 0.0

        df.ix[df.a==0.0,'1D Intensity'] = (df['E'] /(2.0*numpy.pi*r)) *(numpy.pi/2.0)
        del df['a']

        df['2D Intensity'] =  df2['Total Trace Length'] / df4['Area']
        df['Dimensionless Intensity'] = df['2D Intensity'] * df['Average Branch Length']

        writer = pd.ExcelWriter(output, engine='xlsxwriter')

        df = pd.concat([df4,df,df3,df2],axis=1)

        df = df[numpy.isfinite(df['No. Nodes'])]
        df.replace(numpy.inf, 0.0,inplace=True)
        df.replace(numpy.nan, 0.0,inplace=True)
        df = df.round(5)

        df.to_excel(writer,'Data') #Format Excel
        workbook = writer.book
        worksheet = writer.sheets['Data']
        format1 = workbook.add_format({'num_format': '0.00','bg_color':'87ceeb','border':1,'border_color':'696969'})
        format1_2 = workbook.add_format({'num_format': '0.00','bg_color':'6095DA','border':1,'border_color':'696969'})
        format2 = workbook.add_format({'num_format': '0.00','bg_color':'BEF781','border':1,'border_color':'696969'})
        format2_2 = workbook.add_format({'num_format': '0.00','bg_color':'01DF74','border':1,'border_color':'696969'})
        format3 = workbook.add_format({'num_format': '0.00'})

        worksheet.set_column('A:C',16,format3)
        worksheet.set_column('D:I',21,format1)
        worksheet.set_column('J:V',21,format1_2)
        worksheet.set_column('W:AC',16,format2)
        worksheet.set_column('AD:AJ',16,format2_2)

        count = len(df)+ 1
        for n in range(100):
            worksheet.set_row(count,15,format3)
            count += 1

        writer.save()

        os.remove(inFC)
        os.remove(inFC2)
        os.remove(inFC3)


    except Exception,e:
        print e
        time.sleep(5)


if __name__ == "__main__":

    try:
        inFC = sys.argv[1]
        inFC2 = sys.argv[2]
        inFC3 = sys.argv[3]
        output = sys.argv[4]

        main(inFC,inFC2,inFC3,output)

    except Exception,e:
        print '%s e'%(e)
        time.sleep(10)
