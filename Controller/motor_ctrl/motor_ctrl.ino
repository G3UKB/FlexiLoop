/*
* motor_ctrl.ino
*
* Motor control
* 
* Copyright (C) 2025 by G3UKB Bob Cowdery
* This program is free software; you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation; either version 2 of the License, or
* (at your option) any later version.
*    
*  This program is distributed in the hope that it will be useful,
*  but WITHOUT ANY WARRANTY; without even the implied warranty of
*  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
*  GNU General Public License for more details.
*    
*  You should have received a copy of the GNU General Public License
*  along with this program; if not, write to the Free Software
*  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*    
*  The author can be reached by email at:   
*     bob@bobcowdery.plus.com
*
*/

/*
* Responsible for motor drive using potentiometer feedback.
* Driver level code is a request/response architecture.
* The only autominous aspect is status, limits and debug
* reporting during move operations.
*/

// Motor driver lib
#include "DualMC33926MotorShield.h"

// Constants
// Change pin assignments here
#define POTENTIOMETER_PIN A3
#define RLY_PIN 22
#define TRUE 1
#define FALSE 0
#define FORWARD 0
#define REVERSE 1
#define HOME 0
#define MAX 1
// Speed mid point
#define DEFAULT_SPEED 200
// Loop iteration rate in ms
#define TICK 100
#define FB_COUNT 10

// Instance of motor driver
DualMC33926MotorShield md;
int current_speed = DEFAULT_SPEED; // Current speed in range 0 to +-400
// Param stack for debug messages
int p[10];
// Track feedback values
int fb_val = -1;
// Limits
int home_limit = -1;
int max_limit = -1;

// ******************************************************************
// Entry point, runs once on power-on
void setup() {
  // We use a simple text serial protocol between RPi and ourselves
  Serial.begin(9600);
  // Initialise motor driver
  md.init();
  // Set pin modes and set default relay state
  pinMode(POTENTIOMETER_PIN, INPUT);
  pinMode(RLY_PIN, OUTPUT);
  digitalWrite(RLY_PIN, HIGH);
}

// ******************************************************************
// Execution loop runs continuously
void loop() {
  // Wait for a command, execute and respond
  if (Serial.available() > 0) {
    // We have some data in the buffer
    // Read until terminator
    String data = Serial.readStringUntil(';');
    // Ececute command and return response
    process(data);
  }
  // Wait TICK ms
  delay (TICK);
}

// ******************************************************************
// Process command
void process(String data) {
  /*
  * Commands consist of:
  *   A single command character followed by one or more arguments.
  *
  *   Protocol is variable length:
  *   Command character followed by one or more optional arguments.
  *     command, [arg.arg.arg. ...];
  *     
  * Command set:
  *   o Relay energise : a;
  *   o Relay de-energise : b;
  *   o Free run forward : c;
  *   o Free run reverse : d;
  *   o Stop free run : e;
  *   o Nudge forward : f;
  *   o Move to home position : h;
  *   o Set home limit : j, pos as int [0 to 1023].;
  *   o Set max limit : k, pos as int [0 to 1023].;
  *   o Move to position : m, pos as int [0 to 1023].;
  *   o Get position value : p;
  *   o Nudge reverse : r;
  *   o Set speed : s, speed.;
  *   o Run reverse for n ms : v,n.;
  *   o Run forward for n ms : w,n.;
  *   o Move to max extension : x;
  *   o Heartbeat : y;
  *   o Abort : z;
  *
  * Special commands:
  * Heartbeat - this is not a user mode request. It should be executed
  *   periodically in the command execution chain of the caller to ensure
  *   we are still on-line. The response is 'y;'.
  *
  * Abort - this command can be sent at any time whilst there is a move
  *   in progress to abort the move. If there is nothing in progress
  *   it has null effect. There is no response to an Abort. The operation
  *   being aborted will complete prematurely without error.
  *
  * Stop free run - The commands run forward and run reverse simply runs the
  *   motor forward or reverse. During the run the stop command can be sent at
  *   any time and will cause the current move to stop and complete. The stop
  *   command itself has no response. The limits are also monitored and will
  *   perform an auto-stop should one be detected.
  *
  * Responses take the form:
  *   name; i.e. Speed;
  *     or
  *   name: value; i.e. Pos:feedback val;
  * Autominous messages:
  *   Status: feedback val;
  *   Dbg:msg [arg/arg/arg/ ...]; (coded as required, msg and args are the message text)
  *   e.g.
  *     p[0] = fb_val;
  *     p[1] = last_fb_val;
  *     debug_print("Pass: ", 2, p);
  *   Limit:h or x; (not implemented)
  */

  // Extract single character command
  char cmd = data[0];

  // There is an issue with the compiler :-
  // If you declare a variable inside a case
  // the code hangs and will never progress 
  // to later cases.
  int ms;
  int speed;
  int val;
  
  // Switch on command type
  switch (cmd) {
    
    case 'a':
      digitalWrite(RLY_PIN, LOW);
      Serial.print("RlyOn;");
      break;

    case 'b':
      digitalWrite(RLY_PIN, HIGH);
      Serial.print("RlyOff;");
      break;

    case 'c':
      move_fwd();
      Serial.print("RunFwd;");
      break;

    case 'd':
      move_rev();
      Serial.print("RunRev;");
      break;

    case 'e':
      stop_move();
      Serial.print("StopRun;");
      break;

    case 'f':
      if (move_ms(20, FORWARD)) {
        Serial.print("NudgeFwd;");
      } else {
        Serial.println("Motor fault on nudge!;");
      }
      break;

    case 'h':
      if (!go_home_or_max(HOME)) {
        Serial.print("Motor fault;");
      };
      Serial.print("Home;");
      break;

    case 'j':
      // Parse out the home value
      val = parse_int(data, 2);
      home_limit = val;
      Serial.print("HomeLimit;");
      break;

    case 'k':
      // Parse out the max value
      val = parse_int(data, 2);
      max_limit = val;
      Serial.print("MaxLimit;");
      break;

    case 'm':
      // Parse out the value to move to
      val = parse_int(data, 2);
      if (move_to_feedback_value(val)) {
        Serial.print("MoveTo: ");
        Serial.print(get_feedback_value());
        Serial.print(';');
      } else {
        Serial.print("Motor fault on move!;");
      }
      break;

    case 'p':
      Serial.print("Pos: ");
      Serial.print(get_feedback_value());
      Serial.print(';');
      break;

    case 'r':
      if (move_ms(20, REVERSE)) {
        Serial.print("NudgeRev;");
      } else {
        Serial.print("Motor fault on nudge!;");
      }
      break;

    case 's':
      // Parse out the speed
      speed = parse_int(data, 2);
      // Set as current speed
      current_speed = speed;
      Serial.print("Speed;");
      break;

    case 'v':
      // Parse out the number of ms
      ms = parse_int(data, 2);

      if (move_ms(ms, REVERSE)) {
        Serial.print("msRev;");
      } else {
        Serial.print("Motor fault on reverse ms!;");
      }
      break;

    case 'w':
      // Parse out the number of ms
      ms = parse_int(data, 2);
      if (move_ms(ms, FORWARD)) {
        Serial.print("msFwd;");
      } else {
        Serial.print("Motor fault on forward ms!;");
      }
      break;

    case 'x':
      if (!go_home_or_max(MAX)) {
        Serial.print("Motor fault;");
      }
      Serial.print("Max;");
      break;

    case 'y':
      // Heartbeat is specifically monitored.
      Serial.print("y;");
      break;

    case 'z':
      // This is an abort which has caught us outside of 
      // the normal 'check for abort' while moving. So may have been 
      // during a position command etc. We don't want to send any response
      // here as it will be an unexpected response and the abort should
      // process normally at the controller level.
      break;

    default:
      Serial.print("Bad cmd!;");
  }
}

// ******************************************************************
// Utility functions
// Parse an int starting at start_at until '.'
int parse_int(String data, int start_at) {
  int val = 0;
  int i,j;
  if (data.length() > 4) {
    String s;
    for (i = start_at, j = 0 ; i < data.length() ; i++, j++) {
      if (data[i] == '.') break;
      s += data[i];
    }
    val = s.toInt();
  }
  return val;
}

// Have we been sent an abort
int check_abort() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil(';');
    if (data[0] == 'z') {
      return TRUE;
    }
  }
  return FALSE;
}

// have we seen a stop command
int check_stop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil(';');
    if (data[0] == 'e') {
      return TRUE;
    }
  }
  return FALSE;
}

// Have we triggered a limit switch
int check_limit() {
  fb_val = get_feedback_value();
  // Test if very near either limit
  if ((home_limit != -1) && (max_limit != -1)) {
    if  (
          (fb_val < home_limit + 2) ||
          (fb_val > max_limit - 2) 
        ) { 
        return TRUE;
    }
  }
  return FALSE;
}

// Status report
void send_status() {
  Serial.print("Status: ");
  Serial.print(get_feedback_value());
  Serial.print(";");
}

// Format and send a debug message
void debug_print(String msg, int num_args, int args[]) {
  int i;
  Serial.print("Dbg: ");
  Serial.print(msg);
  if (num_args > 0) {
    for(i=0; i<num_args; i++) {
      Serial.print(String(args[i]));
      Serial.print("/");
    }
  }
  Serial.print(";");
}

// ******************************************************************
// Execution functions
// Get current feedback pot value (0-1023)
int get_feedback_value() {
  return analogRead(POTENTIOMETER_PIN);
}

// Move to home or max position
int go_home_or_max(int pos) {
  // Assume home is reverse

  // Local vars
  int st_counter = 5;
  int speed;

  // Which way are we going?
  if (pos == HOME) {
    speed = -current_speed;
  } else {
    speed = current_speed;
  }

  // Set speed and test we are go
  md.setM1Speed(speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    // We wait until the feedback no longer changes.
    // This means we have hit the limit switch and movement has stopped.
    // Precaution wait
    delay(100);
    // Loop until success or abort
    while(TRUE) {
      // Test for end conditions
      if (check_abort() || check_limit()) {
        break;
      }
      // Time for a status report?
      if (st_counter-- <= 0) {
        st_counter = 5;
        send_status();
      }
      // If we spin too fast the feedback may not change enough and give a false positive
      delay (500);   
    }

    // All done
    delay(100);
    md.setM1Speed(0);
    return TRUE;
  }
}

// Move actuator to given feedback value
int move_to_feedback_value(int target) {
  int counter = 5;
  int current_val = get_feedback_value();
  int speed = 0;
  int dir = FORWARD;
  int end = FALSE;
  if (target > current_val) {
    // Moving forward
    speed = current_speed;
    dir = FORWARD;
  } else {
    // Moving reverse
    speed = -current_speed;
    dir = REVERSE;
  }
  md.setM1Speed(speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    send_status();
    if (dir == FORWARD) {
      while(get_feedback_value() < target) {
        if (counter-- <= 0) {
          counter = 5;
          send_status();
          if (check_abort() || check_limit()) {
            end = TRUE;
            break;
          }
        }
        delay(100);
      }
    } else {
      while(get_feedback_value() > target){
        if (counter-- <= 0) {
          counter = 5;
          send_status();
          if (check_abort() || check_limit()) {
            md.setM1Speed(0);
            end = TRUE;
            break;
          }
        }
        delay(100);
      }
    }

    int l_speed = current_speed;
    if (end == FALSE) {
      // See how close we got
      md.setM1Speed(0);
      delay(500);
      int diff = abs(get_feedback_value() - target);
      if (diff > 1) {
        // More than about 0.2% deviation
        // See if we can do better
        current_speed = 50;  // slow it down
        int attempts = 10;    // Limit this at 10 correction attempts
        int dir;

        // Ensure we take up gear slack in the same direction on every move.
        // If necessary move reverse so adjustment is always moving forward.
        while(get_feedback_value() > target) {
          move_ms(100, REVERSE);
          if (check_abort() || check_limit()) {
            md.setM1Speed(0);
            end = TRUE;
            break;
          }
        }

        if (end == FALSE) {
          diff = abs(get_feedback_value() - target);
          while (diff > 1) {
            if (get_feedback_value() > target) {
              dir = REVERSE;
            } else {
              dir = FORWARD;
            }
            move_ms(50, dir);
            delay(100);
            diff = abs(get_feedback_value() - target);
            if (attempts -- <= 0) {
              break;
            }
            if (check_abort()) {
              break;
            }
          }
        }
      }
    }

    // Stop driving
    current_speed = l_speed;
    md.setM1Speed(0);
    // Final position update
    send_status();
    delay(500);
  }
  return TRUE;
}

// Move forward or reverse for ms milliseconds
int move_ms(int ms, int pos) {
  int speed = 0;

  if (pos == FORWARD) {
    speed = current_speed;
  } else {
    speed = -current_speed;
  }
  md.setM1Speed(speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    delay (ms);
    md.setM1Speed(0);
    send_status();
  }
  return TRUE;
}

// Free move forward
int move_fwd() {
  int counter = 5;
  md.setM1Speed(current_speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    while (!check_stop() && !check_limit()) {
      delay (100);
      if (counter-- <= 0) {
        counter = 5;
        send_status();
      }
    }
  }
  md.setM1Speed(0);
  return TRUE;
}

// Free move reverse
int move_rev() {
  int counter = 5;
  md.setM1Speed(-current_speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    delay (300);
    while (!check_stop() && !check_limit()) {
      delay (100);
      if (counter-- <= 0) {
        counter = 5;
        send_status();
      }
    }
  }
  md.setM1Speed(0);
  return TRUE;
}

// Stop free move
int stop_move() {
  md.setM1Speed(0);
  return TRUE;
}

