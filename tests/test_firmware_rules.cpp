#include "../firmware/esp32/rules.hpp"
#include <cassert>
int main(){
  ThresholdRule r;
  assert(r.update(36,true,35,33,3)==0);assert(r.update(36,true,35,33,3)==0);assert(r.update(36,true,35,33,3)==1);
  assert(r.active);assert(r.update(0,false,35,33,3)==0);assert(r.active);
  assert(r.update(34,true,35,33,3)==0);assert(r.active);
  assert(r.update(32,true,35,33,3)==0);assert(r.update(32,true,35,33,3)==0);assert(r.update(32,true,35,33,3)==-1);
  DebouncedInput d;assert(!d.update(true,100));assert(!d.update(false,110));assert(!d.update(true,120));assert(!d.update(true,160));assert(d.update(true,170));assert(d.stable);
  DebouncedInput wrap;assert(!wrap.update(true,0xfffffff0));assert(wrap.update(true,40));
}
