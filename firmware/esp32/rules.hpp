#pragma once
#include <stdint.h>
struct ThresholdRule {
  bool active=false;
  unsigned count=0;
  // Return 1 on activation, -1 on clearing, 0 when unchanged.
  int update(float value,bool valid,float high,float clear,unsigned required) {
    if(!valid){count=0;return 0;}
    bool crossed=active ? value<clear : value>high;
    count=crossed ? count+1 : 0;
    if(count>=required){active=!active;count=0;return active?1:-1;}
    return 0;
  }
};
struct DebouncedInput {
  bool stable=false,candidate=false;
  uint32_t since=0;
  bool update(bool raw,uint32_t now,uint32_t delayMs=50) {
    if(raw!=candidate){candidate=raw;since=now;}
    if(stable!=candidate && uint32_t(now-since)>=delayMs){stable=candidate;return true;}
    return false;
  }
};
