#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""
Description: This app is used to parse the main log file and get the information of VoLTE video call
Version-0.4
Author: yi.qiu
E-mail:yi.qiu@spreadtrum.com
Date: 2016-02-15
Date: 2016-03-04
Date: 2016-04-25
"""

import sys
import tkinter.filedialog
import tkinter.messagebox
import tkinter
import os
import platform
import time
import csv
import threading

"""================================================== Macro ====================================================="""
CALL_END_STATE = 0      #THE VT is finished or not ready started
CALL_ACTIVE_STATE = 1   #THE VT is active
CALL_RINGING_STATE = 2  #THE VT is ringing

CALL_START_KEY = "_VTSP_CMD_STREAM_VIDEO_START"
CALL_ACTIVE_KEY = "VTSP_STREAM_DIR_SENDRECV"
#CALL_ACTIVE_KEY1 = "VTSP_STREAM_DIR_RECVONLY"
CALL_END_KEY = "_VTSP_CMD_STREAM_VIDEO_END"
CALL_DATA_KEY = "_VIER_netSocketReceiveFrom"
CALL_RESOLUTION_OR_KEY1 = "CAMERA_SIZE"
CALL_RESOLUTION_OR_KEY2 = "updateVideoParameter, size"

CALL_DOWNLINK_BITRATE_AND_KEY1 = 'bitrate_kbps'
CALL_DOWNLINK_BITRATE_AND_KEY2 = '_VC_rtcpUtilRunTmmbrFsm2'
CALL_TMMBR_AND_KEY1 = 'sendTmmbrInKbps'
CALL_TMMBR_AND_KEY2 = '_VC_rtcpUtilRunTmmbrFsm2'

CALL_UPLINK_BITRATE_AND_KEY1 = 'VideoCallEngineClient'
CALL_UPLINK_BITRATE_AND_KEY2 = 'bitrate_act'
CALL_RECV_TMMBR_AND_KEY1 = 'VideoCallEngineClient'
CALL_RECV_TMMBR_AND_KEY2 = 'VC_EVENT_REMOTE_RECV_BW_KBPS'

RTP_SEQUENCE_GAP = 2000
APP_VERSION = 0.4
LOG_YEAR = '2016-'
"""==============================================================================================================="""

"""======================================record every vt call status=============================================="""
class vt_statistics:
    def __init__(self):
        self.ring_time = ''
        self.call_start_time = ''
        self.call_end_time = ''
        self.resolution = ''
        self.loss_rate = -1
        self.tol_num = 0
        self.flag_bad = False
        self.rx_info_list = []      #[[SEQn, NUMn], ...]
        self.state = CALL_END_STATE
        self.loss_range = []        #[loss_rate, [SEQ1, NUM1], [SEQ2, NUM2]]
        self.br_info = []           #[[time_stamp, bitrate, loss_rate, tmmbr_sent], ...]
        self.enc_info = []          #[[time_stamp, bitrate_act, frame_rate],...]
        self.enc_stat = []          #[min, max, avrg] int(Kbps)

    def get_date(self, date_str, is_split = True):
        if is_split:
            if 'A' in date_str:
                date = (LOG_YEAR + date_str[2:]).strip().split('.') # to support the ylog
            else:
                date = (LOG_YEAR + date_str).strip().split('.')
        else:
            if 'A' in date_str:
                date = (date_str[2:]).strip()
            else:
                date = (date_str).strip()
        return date

    def call_ring(self, line):
        """update the state, when the call is ringing"""
        temp = line.strip().split('  ')
        #update the call state
        self.state = CALL_RINGING_STATE
        self.ring_time = self.get_date(temp.pop(0), False)

    def call_end(self, line):
        """update the state, when the call is end"""
        temp = line.strip().split('  ')
        #update the call state
        self.state = CALL_END_STATE
        self.call_end_time = self.get_date(temp.pop(0), False)
        #self.calc_loss_rate()
        self.get_loss_peek_range()
        self.cal_enc_statistics()

    def call_active(self, line):
        """update the state, when the call is active"""
        temp = line.strip().split('  ')
        #update the call state
        self.state = CALL_ACTIVE_STATE
        self.call_start_time = self.get_date(temp.pop(0), False)
    def cal_enc_statistics(self):
        if len(self.enc_info) > 0:
            data = [each[1] for each in self.enc_info]
            self.enc_stat.append(min(data))
            self.enc_stat.append(max(data))
            self.enc_stat.append(int(sum(data)/len(self.enc_info)))

    def get_rx_info(self, line):
        """get the rx info from the log line and keep it in the list"""
        temp = line.strip().split(' = ')
        rxn = int(temp[-1])
        temp2 = temp[-2].strip().split(',')
        seqn = int(temp2[0])
        #insert a new data info into rx_info_list
        self.rx_info_list.append([seqn, rxn])

    def get_resolution(self, line):
        """get the video resolution"""
        #if self.resolution == '':
        if CALL_RESOLUTION_OR_KEY1 in line:
            temp = line.strip().split(' ')
            self.resolution = temp[-1]
        elif CALL_RESOLUTION_OR_KEY2 in line:
            temp = line.strip().split(',')
            self.resolution = temp[1] + ', ' + temp[2]


        #print(self.resolution)
    def get_bitrate_info(self, line):
        """get the bitrate information"""
        data = []
        temp = line.strip().split('  ')
        date = self.get_date(temp.pop(0))

        ts = time.mktime(time.strptime(date[0], '%Y-%m-%d %H:%M:%S')) + float(date[1])/1000
        #insert the time stamp
        data.append(ts)

        #temp[-1] = ' : _VC_rtcpUtilRunTmmbrFsm2: TMMBR - state:0 dir:1 bitrate_kbps: 0 expected:1 lost:1'
        temp2 = temp[-1].strip().split('bitrate_kbps:')
        temp = temp2[1].strip().split(' ')
        #insert the bitrate in Kbps
        data.append(int(temp.pop(0)))

        #temp = ['expected:1', 'lost:1']
        temp2 = (temp.pop(0)).strip().split(':')
        ecnt = float(temp2[1])
        temp2 = (temp.pop(0)).strip().split(':')

        lcnt = float(temp2[1])
        #insert the loss rate
        if (lcnt >= ecnt and ecnt > 10):
            data.append(100.0)
        elif (lcnt >= ecnt and ecnt <= 10) or (ecnt == 0) :
            data.append(0.0)
        else:
            data.append(lcnt/ecnt * 100)

        #insert the TMMBR value 0
        data.append(0)

        self.br_info.append(data)

    def get_tmmbr_sent_info(self, line):
        data = []
        temp = line.strip().split('  ')
        date = self.get_date(temp.pop(0))

        ts = time.mktime(time.strptime(date[0], '%Y-%m-%d %H:%M:%S')) + float(date[1])/1000
        #insert the time stamp
        data.append(ts)

        #temp[-1] = ' : _VC_rtcpUtilRunTmmbrFsm2: TMMBR - state:0->1, dir:1->3, sendTmmbrInKbps:526, step:131, lost_permillage:38, mask:0x80'
        temp2 = temp[-1].strip().split('sendTmmbrInKbps:')
        temp = temp2[-1].strip().split(',')
        tmmbr = int(temp.pop(0))
        step = int(temp.pop(0).strip().split(':')[1])
        lrate = float(temp.pop(0).strip().split(':')[1])/10

        if (len(self.br_info) > 0):
            data.append(self.br_info[-1][1])
        else:
            data.append(tmmbr + step)
        data.append(lrate)
        data.append(tmmbr)

        self.br_info.append(data)

    def get_enc_bitrate_info(self, line):
        data = []
        temp = line.strip().split('  ')
        date = self.get_date(temp.pop(0))
        #date = (LOG_YEAR + temp.pop(0)).strip().split('.')
        ts = time.mktime(time.strptime(date[0], '%Y-%m-%d %H:%M:%S')) + float(date[1])/1000
        #insert the time stamp
        data.append(ts)

        #[' 203', '2578 I VideoCallEngineClient: bitrate_act 593187 bps, frame rate 29 fps, start_tm 147652858885, stop_tm 147652858885, enc_tol_size 222816, frame_tol_num 90']
        temp2 = (temp[-1].strip().split('bitrate_act '))[-1]
        #insert the bitrate (Kbps)
        data.append(int(int(temp2.strip().split(' ')[0]) / 1000))  #(bps -> Kbps)
        #insert the frame rate (fps)
        data.append(int(temp2.strip().split(' ')[3]))

        self.enc_info.append(data)
        pass
    def get_loss_peek_range(self):
        """calculate the loss rate of current video call"""
        if (len(self.rx_info_list) < 2):
            return

        temp = [0]
        first_idx = 1
        wrap_cnt = 0
        is_wrap = False

        for index in range(1, len(self.rx_info_list), 1):
            seq1 = self.rx_info_list[index-1][0]
            num1 = self.rx_info_list[index-1][1]
            seq2 = self.rx_info_list[index][0]
            num2 = self.rx_info_list[index][1]
            # if seq overflow happens, wrap_cnt ++
            if (seq1 > seq2):
                if (seq1 > seq2 + RTP_SEQUENCE_GAP):
                    is_wrap = True
                    wrap_cnt = wrap_cnt + 1
                else:
                    # the sequence of RTP is not sequencial, maybe the some logs are lost
                    wrap_cnt = 0
                    self.flag_bad = True
                    continue
            elif (seq2 > seq1 + RTP_SEQUENCE_GAP):
                # the sequence of RTP is not sequencial, maybe the some logs are lost
                wrap_cnt = 0
                self.flag_bad = True
                continue

            if (self.flag_bad or seq1 == seq2):
                loss = 0
            else:
                seq2 = seq2 if not is_wrap else (seq2 + 65536)
                loss = ((seq2 - seq1)-(num2 - num1))/(seq2 - seq1)
                is_wrap = False

            if loss < 0:
                loss = 0
            temp.append(loss * 100)

        #bingo, record the most loss range
        index2 = temp.index(max(temp))
        self.loss_range.append(max(temp))
        self.loss_range.append(self.rx_info_list[index2 - 1])  #insert [seq1, num1]
        self.loss_range.append(self.rx_info_list[index2])      #insert [seq2, num2]
        #print('biggest partial loss rate %.2f'%max(temp), '%    range: ',self.loss_range)

        #calculate the loss rate of this call
        if (self.flag_bad == False):
            seq1 = self.rx_info_list[0][0]
            num1 = self.rx_info_list[0][1]
            seq2 = self.rx_info_list[-1][0]
            num2 = self.rx_info_list[-1][1]
            seq2 = 65536 * wrap_cnt + seq2
            if (seq1 == seq2):
                self.loss_rate = 0
            else:
                self.loss_rate = ((seq2 - seq1)-(num2 - num1))/(seq2 - seq1) * 100
        self.tol_num = num2 - num1
    def show(self, text):
        text.insert(tkinter.END, 'Time of preparation: %s\n'%self.ring_time)
        text.insert(tkinter.END, 'Time of start: %s\n'%self.call_start_time)
        text.insert(tkinter.END, 'Time of termination: %s\n'%self.call_end_time)
        text.insert(tkinter.END, 'Resolution: %s\n'%self.resolution)
        text.insert(tkinter.END, 'RTP loss rate: %.2f%s    total num: %d\n'%(self.loss_rate, '%', self.tol_num))
        if self.loss_rate > 0:
            text.insert(tkinter.END, 'Highlight sequence range of losing RTP: [%d, %d]  %.2f%s\n' \
                        %(self.loss_range[1][0], self.loss_range[2][0], self.loss_range[0], '%'))
        if (len(self.enc_stat) > 0):
            text.insert(tkinter.END, 'Encode bitrate statistics(Kbps): min:%d  max:%d  avrg:%d\n' \
                        %(self.enc_stat[0], self.enc_stat[1], self.enc_stat[2]))

    def export_brinfo2csv(self, file_path):
        if (len(self.br_info) == 0) or (self.tol_num == 0):
            return True

        if os.path.exists(file_path):
            open_mode = 'w'
        else:
            open_mode = 'x'

        try:
            with open(file_path, open_mode, newline='') as csv_file:
                writer = csv.writer(csv_file)
                head = ['time_stamp(ms)', 'bitrate(Kbps)', 'loss_rate(%)', 'tmmbr_sent(Kbps)']
                writer.writerow(head)

                if (self.call_start_time != '') :
                    date = self.get_date(self.call_start_time)
                    #date = (LOG_YEAR + self.call_start_time).strip().split('.')
                    ts_first = time.mktime(time.strptime(date[0], '%Y-%m-%d %H:%M:%S')) + float(date[1])/1000
                else :
                    ts_first = self.br_info[0][0]

                for each_elem in self.br_info:
                    data = each_elem
                    data[0] = int((each_elem[0] - ts_first) * 1000)
                    writer.writerow(data)
                return True
        except IOError:
            wrong_str = 'Failed to open ' + file_path
            tkinter.messagebox.showerror('ERROR', wrong_str)
            return False
    def export_encinfo2csv(self, file_path):
        if (len(self.enc_info) == 0) or (self.tol_num == 0):
            return True

        if os.path.exists(file_path):
            open_mode = 'w'
        else:
            open_mode = 'x'

        try:
            with open(file_path, open_mode, newline='') as csv_file:
                writer = csv.writer(csv_file)
                head = ['time_stamp(ms)', 'bitrate(Kbps)', 'frame_rate(fps)']
                writer.writerow(head)
                ts_first = self.enc_info[0][0]
                for each_elem in self.enc_info:
                    data = each_elem
                    data[0] = int((each_elem[0] - ts_first) * 1000)
                    writer.writerow(data)
                return True
        except IOError:
            wrong_str = 'Failed to open ' + file_path
            tkinter.messagebox.showerror('ERROR', wrong_str)
            return False
"""==============================================================================================================="""



"""========================================list for record all vt call status====================================="""
class vt_list:
    def __init__(self):
        self.list = []
        self.num = 0
        self.flag = 0

    def parse(self, line):
        """parse the main.log"""
        if CALL_START_KEY in line:
            #add a new vt into the list
            elem = vt_statistics()
            self.list.append(elem)
            self.num = self.num + 1
            elem.call_ring(line)
            self.flag = 1
        elif ((CALL_END_KEY in line) or (line == '')):
            if self.flag == 1:
                elem = self.list[self.num - 1]
                elem.call_end(line)
                self.flag = 0
        elif CALL_ACTIVE_KEY in line:
            if self.flag == 0:
                elem = vt_statistics()
                self.list.append(elem)
                self.num = self.num + 1
            elem = self.list[self.num - 1]
            elem.call_active(line)
            self.flag = 1
        elif CALL_DATA_KEY in line:
            if self.flag == 0:
                return
            elem = self.list[self.num - 1]
            elem.get_rx_info(line)
        elif CALL_RESOLUTION_OR_KEY1 in line or \
             CALL_RESOLUTION_OR_KEY2 in line:
            if self.flag == 0:
                return
            elem = self.list[self.num - 1]
            elem.get_resolution(line)
        elif (CALL_DOWNLINK_BITRATE_AND_KEY1 in line) and \
             (CALL_DOWNLINK_BITRATE_AND_KEY2 in line):
            if self.flag == 0:
                return
            elem = self.list[self.num - 1]
            elem.get_bitrate_info(line)

        elif (CALL_TMMBR_AND_KEY1 in line) and \
             (CALL_TMMBR_AND_KEY2 in line):
            if self.flag == 0:
                return
            elem = self.list[self.num - 1]
            elem.get_tmmbr_sent_info(line)
        elif (CALL_UPLINK_BITRATE_AND_KEY1 in line) and \
             (CALL_UPLINK_BITRATE_AND_KEY2 in line):
            if self.flag == 0:
                return
            elem = self.list[self.num - 1]
            elem.get_enc_bitrate_info(line)

    def print_result(self, text):
        """print the result"""
        num = 1
        for elem in self.list:
            text.insert(tkinter.END, "\n=========================CALL %d=============================\n"%num)
            elem.show(text)
            num = num + 1

    def clear_all(self):
        """clear the member para"""
        self.num = 0
        self.flag = 0
        self.list = []
    def export_csv(self, cur_dir):
        """ export csv files"""
        index = 1
        ret = True

        for elem in self.list:
            file_path = cur_dir + 'call_dl_' + str(index) + '.csv'
            ret = elem.export_brinfo2csv(file_path)
            if (ret == False):
                break
            file_path = cur_dir + 'call_ul_' + str(index) + '.csv'
            ret = elem.export_encinfo2csv(file_path)
            if (ret == False):
                break
            index = index + 1

        if (ret):
            tkinter.messagebox.showinfo('Export CSV', 'Succeed')

"""==============================================================================================================="""


"""============================================= mainframe of the App============================================="""
class mainframe:
    def __init__(self, sdata, run = True):
        """constructor of mainframe"""
        self.top = tkinter.Tk()
        self.top.title("VLP--VoLTE Log Parser_%s"%APP_VERSION)
        self.text = self.create_text(self.top)
        self.create_menu(self.top)
        self.log_path = ''
        self.sdata = sdata
        sdata.set_text(self.text)
        self.report = sdata.get_report_instance()
        self.top.mainloop()

    def open_and_parse(self):
        """open the main log file and parse it"""
        if (self.sdata.is_busy()):
            tkinter.messagebox.showwarning('Save Report', 'It\'s busy now, try it later.')
            return
        self.log_path = tkinter.filedialog.askopenfilename()
        self.report.clear_all()
        with self.sdata.lock4cond:
            self.sdata.set_log_path(self.log_path)
            self.sdata.set_busy()
            self.sdata.cond.notify()

    def export_csv(self):
        """ export csv files """
        if (self.log_path == ''):
            tkinter.messagebox.showwarning('Save Report', 'Are you kidding me?\nOpen a log file first.')
            return
        if (self.sdata.is_busy()):
            tkinter.messagebox.showwarning('Save Report', 'It\'s busy now, try it later.')
            return

        temp = self.log_path.strip().split('/')
        temp.pop(-1)
        cur_dir = ''
        for i in temp:
            cur_dir = cur_dir + i + '/'
        self.report.export_csv(cur_dir)
        pass

    def clear_text(self):
        """clear the context in the text"""
        if (self.sdata.is_busy()):
            tkinter.messagebox.showwarning('Save Report', 'It\'s busy now, try it later.')
            return
        self.text.delete(1.0, tkinter.END)

    def ask_clear(self):
        """ask whether clear the context in the text"""
        if (self.sdata.is_busy()):
            tkinter.messagebox.showwarning('Save Report', 'It\'s busy now, try it later.')
            return
        if tkinter.messagebox.askokcancel('Clear Report', 'Are you sure to clear them all?'):
            self.clear_text()

    def save_to_file(self):
        """save the report to a file"""
        if (self.sdata.is_busy()):
            tkinter.messagebox.showwarning('Save Report', 'It\'s busy now, try it later.')
            return
        report_path = tkinter.filedialog.asksaveasfilename()
        if (self.log_path == report_path) and (report_path != ''):
            tkinter.messagebox.showwarning('Save Report', 'Never cover source log file!')
            return
        elif self.log_path == '':
            tkinter.messagebox.showwarning('Save Report', 'Are you kidding me?\nOpen a log file first.')
            return
        try:
            with open(report_path, 'w', encoding= 'utf-8') as out_file:
                if (len(self.text.get(1.0, tkinter.END))  > 1):
                    print(self.text.get(1.0, tkinter.END), file=out_file)
                    tkinter.messagebox.showinfo('Save Report', 'Succeed')
                else:
                    tkinter.messagebox.showwarning('Save Report', 'Save nothing.\nThe report is empty.')
        except IOError:
            if report_path == '':
                pass
            else:
                self.clear_text()
                self.text.insert(1.0, "=========================FAIL TO OPEN =========================\n")

    def create_text(self, top):
        """create the text item"""
        text = tkinter.Text(top)
        text.pack(expand=True, fill=tkinter.BOTH)
        text.insert(1.0, "Open a main log file:\n")
        return text

    def create_menu(self, top):
        """create the menu item"""
        menubar = tkinter.Menu(top)
        filemenu = tkinter.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Log", command=self.open_and_parse)
        filemenu.add_command(label="Export CSV", command=self.export_csv)
        filemenu.add_command(label="Save Report", command=self.save_to_file)
        filemenu.add_command(label="Clear Report", command=self.ask_clear)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=top.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        top.config(menu=menubar)

"""==============================================================================================================="""
class share_data:
    def __init__(self):
        self.lock4cond = threading.Lock()
        self.cond = threading.Condition(lock=self.lock4cond)
        self.log_path = ''
        self.parse_stop = False
        self.busy = False
        self.text = None # assigned by mainframe
        self.report = vt_list()
    def is_busy(self):
        return self.busy
    def set_busy(self):
        self.busy = True
    def clean_busy(self):
        self.busy = False
    def get_log_path(self):
        return self.log_path
    def set_log_path(self, file_path):
        self.log_path = file_path
    def clean_log_path(self):
        set_log_path(self, '')
    def is_parse_stop(self):
        return self.parse_stop
    def set_parse_stop(self):
        self.parse_stop = True
    def set_text(self, text):
        self.text = text
    def get_text(self):
        return self.text
    def get_report_instance(self):
        return self.report


"""==========================================Managger of the App================================================="""


class mngr:
    def __init__(self):
        self.sdata  = share_data()
    def predicate_func(self):
        return (self.sdata.is_busy() or self.sdata.is_parse_stop())
    def parse_func(self):
        while(True):
            with self.sdata.lock4cond:
                if self.sdata.cond.wait_for(self.predicate_func):
                    if (self.sdata.is_parse_stop()):
                        break;
                    text = self.sdata.get_text()
                    log_path = self.sdata.get_log_path()
                    try:
                        with open(log_path,'r',encoding= 'utf-8') as log_data:
                            text.delete(1.0, tkinter.END)
                            text.insert(1.0, "Open a main log file:\n")
                            text.insert(tkinter.END, '%s\n\n'%log_path)
                            text.insert(4.0, " Processed 0 lines\n")

                            lcnt = 0
                            ecnt = 0
                            while not self.sdata.is_parse_stop():
                                try:
                                    each_line = log_data.readline()
                                    self.sdata.report.parse(each_line)

                                    if each_line == '':
                                        break;
                                    lcnt = lcnt + 1
                                    if (lcnt & 0x3fff == 0):
                                        text.delete(4.1, tkinter.END)
                                        text.insert(4.0, " Processed %d lines\n"%lcnt)
                                except: #UnicodeDecodeError:
                                    # ignore the devode error
                                    ecnt = ecnt + 1
                                    pass
                            if (self.sdata.is_parse_stop()):
                                return
                            text.delete(4.1, tkinter.END)
                            text.insert(4.0, " Processed %d lines, %d decode errors\n"%(lcnt, ecnt))
                            self.sdata.report.print_result(text)
                    except IOError:
                        if self.sdata.get_log_path() == '':
                            pass
                        else:
                            text.delete(1.0, tkinter.END)
                            text.insert(1.0, "=========================FAIL TO OPEN =========================\n")
                self.sdata.clean_busy()
    def run(self):
        #The mainframe will cause Error when it terminates in one spawned thread instead of the main thread.
        #Error: Tcl_AsyncDelete Error Multithreading Python
        #http://stackoverflow.com/questions/27073762/tcl-asyncdelete-error-multithreading-python
        #
        #thrd_main = threading.Thread(target=self.mainframe_func, name="mainframe")
        #thrd_main.start()
        #while(thrd_main.is_alive()):
        #    thrd_main.join()

        thrd_parse = threading.Thread(target=self.parse_func, name="parser")
        thrd_parse.start()
        mainframe(self.sdata)

        self.sdata.set_parse_stop()
        with self.sdata.lock4cond:
            self.sdata.cond.notify()
        while(thrd_parse.is_alive()):
            thrd_parse.join()
"""==============================================================================================================="""

#=============================== Run main() ======================================
if __name__ == '__main__':
    #import wingdbstub
    manager = mngr()
    manager.run()
