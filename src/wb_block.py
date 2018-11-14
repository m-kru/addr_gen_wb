""" 
This is the script that generates the VHDL code needed to access 
the registers in a hierarchical Wishbone-conencted system.

Written by Wojciech M. Zabolotny
(wzab01@gmail.com or wzab@ise.pw.edu.pl)

The code is published under LGPL V2 license

This file implements the class handling a Wishbone connected block
"""
import re

# Template for generation of the VHDL package
templ_pkg = """\
library ieee;

use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library work;
use work.wishbone_pkg.all;

package {p_entity}_pkg is
{p_package}
end {p_entity}_pkg

package_body {p_entity}_pkg is
{p_package_body}
end {p_entity}_pkg
"""

# Template for generation of the VHDL code

templ_wb = """\
--- This code is automatically generated by the addrgen_wb.py tool
--- Please don't edit it manaully, unless you really have to do it.

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library work;
use work.wishbone_pkg.all;
use work.{p_entity}_pkg.all

entity {p_entity} is
  generic (
    base_addr : unsigned(31 downto 0);
    valid_bits : integer := {valid_bits};
  );
  port (
    rst_n_i : in std_logic;
    clk_sys_i : in std_logic
    slave_i : t_wishbone_slave_in;
    slave_o : t_wishbone_slave_out;
{subblk_busses}
{signal_ports}
    );

end wb_test_top;

architecture gener of {p_entity} is
{signal_decls}
  -- Internal WB declaration
  signal int_regs_wb_s_o : t_wishbone_slave_out;
  signal int_regs_wb_s_i : t_wishbone_slave_in;
  signal int_addr : std_logic_vector({valid_bits}-1 downto 0);
  signal wb_s_out : t_wishbone_slave_out_array(0 to {nof_subblks});
  signal wb_s_in : t_wishbone_slave_in_array(0 to {nof_subblks});

  -- Constants
  constant block_id_addr : std_logic_vector({valid_bits}-1 downto 0) := (others => '0');
  constant block_ver_addr : std_logic_vector({valid_bits}-1 downto 0) := (0=>'1', 'others => '0');

begin
  int_addr <= int_regs_wb_s_i.adr({valid_bits}-1 downto 0);

-- Main crossbar 
  xwb_crossbar_1: entity work.xwb_crossbar
  generic map (
     g_num_masters => 1,
     g_num_slaves  => 1+nof_subblks,
     g_registered  => {p_registered},
     g_address     => {p_addresses},
     g_mask        => {p_masks})
  port map (
     clk_sys_i => clk_sys_i,
     rst_n_i   => rst_n_i,
     slave_i   => slave_i,
     slave_o   => slave_o,
     master_i  => wb_s_out,
     master_o  => wb_s_in,
    sdb_sel_o => open);

-- Process for register access
  process(clk_sys_i)
  begin
    if rising_edge(clk_sys_i) then
      if rst_n_i = '0' then
        -- Reset of the core
      else
        -- Normal operation
        if (int_regs_wb_s_i.cyc = '1') and (int_regs_wb_s_i.stb = '1') then
          -- Access, now we handle consecutive registers
          case int_addr is
{register_access}
          when block_id_addr =>
             int_regs_wb_s_o.dat <= {block_id};
             int_regs__wb_s_o.ack <= '1';
          when block_ver_addr =>
             int_regs_wb_s_o.dat <= {block_ver};
             int_regs_wb_s_o.ack <= '1';
          when others =>
             int_regs_wb_s_o.dat <= x"A5A5A5A5";
             int_regs_wb_s_o.ack <= '1';
          end case;
        end if;
      end if;
    end if;
  end process;
{cont_assigns}
end architecture;
"""
blocks={}

class wb_field(object):
   def __init__(self,fl,lsb):
      self.name = fl.attrib['name']
      self.lsb = lsb
      self.size = int(fl.attrib['width'])
      self.msb = lsb + self.size - 1
      self.type = fl.get('type','std_logic_vector')
     
          

class wb_reg(object):
   """ The class wb_reg describes a single register
   """
   def __init__(self,el,adr):
       """
       The constructor gets the XML node defining the register
       """
       nregs=int(el.get('reps',1))
       self.regtype = el.tag
       self.type = el.get('type','std_logic_vector')
       self.base = adr
       self.size = nregs
       self.name = el.attrib['name']
       self.ack = int(el.get('ack',0))
       self.stb = int(el.get('stb',0))
       # Read list of fields
       self.fields=[]
       self.free_bit=0
       for fl in el.findall('field'):
           fdef=wb_field(fl,self.free_bit)
           self.free_bit += fdef.size
           if self.free_bit > 32:
              raise Exception("Total width of fields in register " +self.name+ " is above 32-bits")
           self.fields.append(fdef)
       

   def gen_vhdl(self,parent):
       """
       The method generates the VHDL block responsible for access
       to the registers.
       We append our definitions to the appropriate sections
       in the parrent block.
       
       We need to generate two sections:
       * Declaration of signals used to input or output the signal,
          and the optional ACK or STB flags
       * Read or write sequence to be embedded in the process
       """
       dt=""
       dtb=""
       # Generate the type corresponding to the register
       tname = "t_"+self.name
       if len(self.fields) == 0:
          # Simple register, no fields
          dt+="subtype "+tname+" is "+\
             self.type+"(31 downto 0);\n" 
       else:
          # Register with fields, we have to create a record
          dt+="type "+tname+" is record\n"
          for fl in self.fields:
             dt+= "  "+fl.name+":"+fl.type+"("+str(fl.size-1)+" downto 0);\n"
          dt+="end record;\n\n"

          #Conversion function stlv to record
          dt+="function stlv2"+tname+"(x : std_logic_vector) return "+tname+";\n"
          dtb+="function stlv2"+tname+"(x : std_logic_vector) return "+tname+" is\n"
          dtb+="variable res : "+tname+";\n"
          dtb+="begin\n"
          for fl in self.fields:
            dtb+="  res."+fl.name+" := "+fl.type+"(x("+str(fl.msb)+" downto "+str(fl.lsb)+"));\n"
          dtb+="  return res;\n"
          dtb+="end stlv2"+tname+";\n\n"
          
          #conversion function record to stlv
          dt+="function "+tname+"2stlv(x : "+tname+") return std_logic_vector;\n"
          dtb+="function "+tname+"2stlv(x : "+tname+") return std_logic_vector is\n"
          dtb+="variable res : std_logic_vector;\n"
          dtb+="begin\n"
          dtb+="  res := (others => '0');\n"
          for fl in self.fields:
            dtb+="  res("+str(fl.msb)+" downto "+str(fl.lsb)+") := std_logic_vector(x."+fl.name+"));\n"
          dtb+="  return res;\n"
          dtb+="end "+tname+"2stlv;\n\n"
       # If this is a vector of registers, create the array type
       if self.size > 1:
          dt+="type "+tname+"_array is array(0 to "+ str(self.size-1) +") of "+tname+";\n"
       # Append the generated types to the parents package section
       parent.add_templ('p_package',dt,0)
       parent.add_templ('p_package_body',dtb,0)

       # Now generate the entity ports
       sfx = '_i'
       sdir = "in "
       if self.regtype == 'creg':
         sfx = '_o'
         sdir = "out "
       if self.size == 1:
          dt=self.name+sfx+" : "+sdir+" "+tname+";\n"
       else:
          dt=self.name+sfx+" : "+sdir+" "+tname+"_array;\n"
       # Now we generate the STB or ACK ports (if required)
       if self.regtype == 'creg' and self.stb == 1:
          # We need to generate STB output
          pass # To be implemented!
       if self.regtype == 'sreg' and self.ack == 1:
          # We need to generate ACK output
          pass # To be implemented!          
       parent.add_templ('signal_ports',dt,4)
       # Generate the intermediate signals for output ports
       # (because they can't be read back)
       
       # Generate the signal assignment in the process
       for i in range(0,self.size):
          # We prepare the index string used in case if this is a vector of registers
          if self.size > 1:
             ind ="("+str(i)+")"
          else:
             ind = ""
          dt= "when \""+format(self.base+i,"032b")+"\" => -- "+hex(self.base+i)+"\n"
          # The conversion functions
          if len(self.fields)==0:
             conv_fun="std_logic_vector"
             iconv_fun=self.type
          else:
             conv_fun="t_"+self.name+"2stlv"
             iconv_fun="stlv2t_"+self.name
          # Read access
          if self.regtype == 'sreg':
             dt+="   int_regs_wb_s_o.dat <= "+conv_fun+"("+self.name+"_i"+ind+");\n"
          else:
             dt+="   int_regs_wb_s_o.dat <= "+conv_fun+"(int_"+self.name+"_o"+ind+");\n"             
          # Write access
          if self.regtype == 'creg':
             dt+="   if int_regs_wb_s_i.we = '1' then\n"
             dt+="     int_"+self.name+"_o"+ind+") <= "+iconv_fun+"(int_regs_wb_s_i.dat);\n"
             dt+="   end if;\n"
          parent.add_templ('register_access',dt,10)
 
   def gen_pkg(self):
     """
     The method generates the VHDL package code.
     For example the record type to access the bitfields.
     """
     pass

class wb_area(object):
    """ The class representing the address area
    """
    def __init__(self,size,name,obj,reps):
        self.name=name
        self.size=size
        self.obj=obj
        self.adr=0
        self.mask=0
        self.total_size=0
        self.reps=reps
    def sort_key(self):
        return self.size
    
class wb_block(object):
   def __init__(self,el):
     """
     The constructor takes an XML node that describes the block
     It also calculates the number of registers, and creates
     the description of the record
     """
     self.templ_dict={}
     self.name = el.attrib['name']
     # We prepare the list of address areas
     self.areas=[]
     # We prepare the table for storing the registers.
     self.regs=[]
     self.free_reg_addr=2 # The first free address after ID & VER
     # Prepare the list of subblocks
     self.subblks=[]
     for child in el.findall("*"):
         # Now for registers we allocate addresses in order
         # We don't to alignment (yet)
        if child.tag == 'creg':
            # This is a control register
           reg = wb_reg(child,self.free_reg_addr)
           self.free_reg_addr += reg.size
           self.regs.append(reg)
        elif child.tag == 'sreg':
            # This is a status register
           reg = wb_reg(child,self.free_reg_addr)
           self.free_reg_addr += reg.size
           self.regs.append(reg)
        elif child.tag == 'subblock':
            # This is a subblock definition
            # We only add it to the list, the addresses can't be allocated yet
           self.subblks.append(child)
        else:
            # Unknown child
           raise Exception("Unknown node in block: "+el.name)
       # After that procedure, the field free_reg_addr contains
       # the length of the block of internal registers

   def analyze(self):
     # Add the length of the local addresses to the list of areas
     self.areas.append(wb_area(self.free_reg_addr,"int_regs",None,1))
     # Scan the subblocks
     for sblk in self.subblks:
        #@!@ Here we must to correct something! The name of the subblock
        #Is currently lost. We must to decide how it should be passed
        #To the generated code@!@
        bl = blocks[sblk.attrib['type']]
        # If the subblock was not analyzed yet, analyze it now
        if len(bl.areas)==0:
            bl.analyze()
            # Now we can be sure, that it is analyzed, so we can 
            # add its address space to ours.
        # Check if this is a vector of subblocks
        reps = int(sblk.get('reps',1))
        print("reps:"+str(reps))
        # Now recalculate the size of the area, considering possible
        # block repetitions
        addr_size = bl.addr_size * reps
        self.areas.append(wb_area(addr_size,sblk.get('name'),bl,reps))
     # Now we can calculate the total length of address space
     # We use the simplest algorithm - all blocks are sorted,
     # their size is rounded up to the nearest power of 2
     # They are allocated in order.
     cur_base = 0
     self.areas.sort(key=wb_area.sort_key, reverse=True)
     for ar in self.areas:
         if ar.obj==None:
             # This is the register block
             self.reg_base = cur_base
         ar.adr = cur_base
         ar.adr_bits = (ar.size-1).bit_length()
         ar.total_size = 1 << ar.adr_bits
         # Now we shift the position of the next block
         cur_base += ar.total_size
         print("added size:"+str(ar.total_size))
     self.addr_size = cur_base
     # We must adjust the address space to the power of two
     self.adr_bits = (self.addr_size-1).bit_length()
     self.addr_size = 1 << self.adr_bits
     # In fact, here we should be able to generate the HDL code
     
     print('analyze: '+self.name+" addr_size:"+str(self.addr_size))

   def add_templ(self,templ_key,value,indent):
       """ That function adds the new text to the dictionary
           used to fill the templates for code generation.
       """
       if templ_key not in self.templ_dict:
          self.templ_dict[templ_key] = ""
       # Now we add all lines from value, providing the appropriate indentation
       for ln in re.findall(r'.*\n?',value)[:-1]:
          if ln != "":
             self.templ_dict[templ_key] += indent*" " + ln            
     
   def gen_vhdl(self):
       # To fill the template, we must to set the following values:
       # p_entity, valid_bits
       
       # subblk_busses, signal_ports, signal_decls
       # nof_subblks,
       # subblk_assignments,
       # n_slaves,
       # p_registered,
       # p_addresses, p_masks
       # block_id, block_ver - to verify that design matches the software

       # First - generate code for registers
       # We give empty declaration in case if the block does not contain
       # any registers
       self.add_templ('p_package','',0)
       self.add_templ('p_package_body','',0)
       self.add_templ('signal_decls','',0)
       self.add_templ('register_access','',0)
       self.add_templ('subblk_busses','',0)
       for reg in self.regs:
          #generate 
          reg.gen_vhdl(self)
       # Generate code for connection of all areas
       ar_adr_bits=[]
       ar_addresses=[]
       n_ports=0
       dt = ""
       for ar in self.areas:
           if (ar.reps == 1):
              ar.first_port = n_ports
              ar.last_port = n_ports
              n_ports += 1
              ar_addresses.append(ar.adr)
              ar_adr_bits.append(ar.adr_bits)
              #generate the entity port but not for internal registers
              if ar.obj != None:
                 dt = ar.name+"_wb_s_o : out t_wishbone_slave_out;\n"
                 dt += ar.name+"_wb_s_i : in t_wishbone_slave_in;\n"
                 self.add_templ('subblk_busses',dt,4)
              #generate the signal assignment
              dt = "wb_s_o("+str(ar.first_port)+") <= "+ar.name+"_wb_s_i;\n"
              dt += ar.name+"_wb_s_i  <= "+"wb_s_o("+str(ar.first_port)+");\n"
              self.add_templ('cont_assigns',dt,4)
           else: 
              # The area is associated with the vector of subblocks
              ar.first_port = n_ports
              ar.last_port = n_ports+ar.reps-1
              n_ports += ar.reps
              #generate the entity port
              dt = ar.name+"_wb_s_o : out t_wishbone_slave_out_array("+str(ar.first_port)+" to "+str(ar.last_port)+");\n"
              dt += ar.name+"_wb_s_i : in t_wishbone_slave_in_array("+str(ar.first_port)+" to "+str(ar.last_port)+");\n"
              self.add_templ('subblk_busses',dt,4)              
              # Now we have to assign addresses and masks for each subblock and connect the port
              base = ar.adr
              nport = ar.first_port
              for i in range(0,ar.reps):
                 ar_addresses.append(base)
                 base += ar.obj.addr_size
                 ar_adr_bits.append(ar.obj.adr_bits)
                 dt = "wb_s_o("+str(nport)+") <= "+ar.name+"_wb_s_i("+str(i)+");\n"
                 dt = ar.name+"_wb_s_i("+str(i)+")  <= "+"wb_s_o("+str(nport)+");\n"
                 self.add_templ('cont_assigns',dt,4)
                 nport += 1
       #Now generate vectors with addresses and masks
       adrs="("
       masks="("
       for i in range(0,n_ports):
          if i>0:
             adrs+=","
             masks+=","
          adrs +="\""+format(ar_addresses[i],"032b")+"\""
          masks +="\""+format((1<<ar_adr_bits[i])-1,"032b")+"\""
       adrs += ");"
       masks += ");"
       self.add_templ('block_id',"x\"00001234\"",0)
       self.add_templ('block_ver',"x\"12344321\"",0)
       self.add_templ('p_addresses',adrs,0)
       self.add_templ('p_masks',masks,0)
       self.add_templ('p_registered','false',0)
       self.add_templ('nof_subblks',str(n_ports),0)
       self.add_templ('p_entity',self.name+"_wb",0)
       self.add_templ('valid_bits',str(self.adr_bits),0)
       # All template is filled, so we can now generate the files
       print(self.templ_dict)
       with open(self.name+"_wb.vhd","w") as fo:
          fo.write(templ_wb.format(**self.templ_dict))
       with open(self.name+"_pkg.vhd","w") as fo:
          fo.write(templ_pkg.format(**self.templ_dict))
        
       pass
