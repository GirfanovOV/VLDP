class VLDP :
    
    def __init__(self, max_page_num, page_capacity, delta_hist_len=3, DPT_cap=64, DHB_cap=128, OPT_cap=64):
        self.max_page_num = max_page_num
        self.page_capacity = page_capacity
        self.delta_hist_len = delta_hist_len
        self.DPT_cap = DPT_cap
        self.DHB_cap = DHB_cap
        self.OPT_cap = OPT_cap
        
        self.DHB = {}
        self.OPT = {}
        self.DPT = []
        for i in range(self.delta_hist_len):
            self.DPT.append({})
        
        self.prediction = None
    
    def req_page_num(self, req):
        return req.offset // self.page_capacity
    
    def req_page_offset(self, req):
        return req.offset - self.req_page_num(req) * self.page_capacity
        
    def evict_and_add_new_DHB_entry(self, req):
        page = self.req_page_num(req)
        page_offset = self.req_page_offset(req)
        
        last_page_access = page_offset
        last_page_access_len = req.length
        page_delta_hist = []
        page_last_predictor = -1
        
        
        self.DHB[page] = [last_page_access, last_page_access_len, page_delta_hist, page_last_predictor]
        
        if len(self.DHB) > self.DHB_cap:
            self.DHB.pop(list(self.DHB.keys())[0])
        
        self.predict_with_OPT(page_offset)
        
    def predict_with_OPT(self, page_offset):
        if page_offset in self.OPT:
            self.prediction = self.OPT[page_offset]
        else:
            self.prediction = None
            
    def process_DHB_entry(self, req):
        page = self.req_page_num(req)
        curr_page_offset = self.req_page_offset(req)
        new_delta = curr_page_offset - self.DHB[page][0]
        req_len = req.length
        
        if len(self.DHB[page][2]) == 0:
            self.OPT[self.DHB[page][0]] = (curr_page_offset - self.DHB[page][0], req_len)
            if len(self.OPT) > self.OPT_cap:
                del self.OPT[list(self.OPT.keys())[0]]
        
        table = self.DHB[page][3]
        delta_footprint = tuple(self.DHB[page][2][(-1)*(table+1):])
        
        
        if table != -1 and delta_footprint in self.DPT[table]:
            diff = 1 if self.DPT[table][delta_footprint][0] == (new_delta, req_len) else -1
            self.DPT[table][delta_footprint][1] += diff
            if self.DPT[table][delta_footprint][1] < 1:
                if table == 2:
                    del self.DPT[table][delta_footprint]
                elif len(self.DHB[page][2]) > table+1:                   
                    self.DPT[table+1][tuple(self.DHB[page][2][(-1)*(table+2):])] = [(new_delta, req_len), 3]
                    if len(self.DPT[table+1]) > self.DPT_cap:
                        self.DPT[table+1].pop(list(self.DPT[table+1].keys())[0])
                else:
                    self.DPT[table][delta_footprint] = [(new_delta, req_len),3]
                    
        
        self.DHB[page][0] = curr_page_offset
        self.DHB[page][1] = req_len
        self.DHB[page][2].append(new_delta)
        self.DHB[page][2] = self.DHB[page][2][max(-3,(-1)*len(self.DHB[page][2])):]
        self.DHB[page][3] = -1
        
        self.predict_with_DPT(page)
        
    def predict_with_DPT(self, page):
        delta_footprint = tuple(self.DHB[page][2])
        delta_footprint1 = tuple(self.DHB[page][2])
        
        table = -1
        for i in reversed(range(len(delta_footprint))):
            if delta_footprint1 in self.DPT[i]:
                table = i
                break
            delta_footprint1 = delta_footprint1[1:]
        
        if table == -1:
            if len(delta_footprint) > 1 and tuple(delta_footprint[-2:-1]) not in self.DPT[0]:
                self.DPT[0][tuple(delta_footprint[-2:-1])] = [(delta_footprint[-1], self.DHB[page][1]), 3]
            
        else:
            self.prediction = self.DPT[table][delta_footprint1][0]
            self.DHB[page][3] = table
        
            
        
    def process_req(self, req):
        page = self.req_page_num(req)
        if page in self.DHB:
            self.process_DHB_entry(req)
        else:
            self.evict_and_add_new_DHB_entry(req)
        
        tmp = self.prediction
        self.prediction = None
        return tmp