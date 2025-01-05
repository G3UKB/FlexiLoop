/*
*
* Flexi-loop arduino code.
* Responsible for feedback and motor drive
* This level is dumb. It simply does what it is told to do.
*
* Commands :
*   o Set speed (slow, medium, fast)
*   o Move to home position
*   o Move to max extension
*   o Get position value
*   o Move to position 
*   o Nudge forward
*   o Nudge reverse
*   o Run forward for n ms
*   o Run reverse for n ms
*   o Free run forward
*   o Free run reverse
*   o Stop free run
*   o Relay energise
*   o Relay de-energise
*
*/

// Motor driver lib
#include "DualMC33926MotorShield.h"

// Constants
#define POTENTIOMETER_PIN A3
#define FORWARD 0
#define REVERSE 1
#define TRUE 1
#define FALSE 0
#define HOME 0
#define MAX 1
#define RLY_PIN 22
#define DEFAULT_SPEED 200

// Instance of motor driver
DualMC33926MotorShield md;
int current_speed = DEFAULT_SPEED; // Current speed in range 0 to +-400
int p[10];
// Limit switch check
int fb_val = -1;
int last_fb_val = -1;
int fb_counter = 5;

// Setup runs once on startup
void setup() {
  // We use a simple text serial protocol between RPi and ourselves
  Serial.begin(9600);
  // Initialise motor driver
  md.init();
  pinMode(POTENTIOMETER_PIN, INPUT);
  pinMode(RLY_PIN, OUTPUT);
  digitalWrite(RLY_PIN, HIGH);
}

// Execution loop runs continuously
void loop() {
  
  // Wait for a command, execute and respond
  if (Serial.available() > 0) {
    // We have some data in the buffer
    // We expect commands to be \n terminated
    String data = Serial.readStringUntil(';');
    process(data);
  }
  delay (100);
}

// Process command
void process(String data) {
  /*
  * Commands consist of:
  *   a single command character followed by one or more arguments
  *   arguments are command specific, elements are comma separated
  *
  *   Protocol is variable length:
  *     comma separated command
  *     full stop separated parameters
  *     semicolon terminator character
  *   o Heartbeat : y;
  *   o Abort : z;
  *   o Set speed : s, speed.;
  *   o Move to home position : h;
  *   o Move to max extension : x;
  *   o Get position value : p;
  *   o Move to position : m, pos as int [0 to 1023].;
  *   o Nudge forward : f;
  *   o Nudge reverse : r;
  *   o Run forward for n ms : w,n.;
  *   o Run reverse for n ms : v,n.;
  *   o Free run forward : c;
  *   o Free run reverse : d;
  *   o Stop free run : e;
  *   o Relay energise : a;
  *   o Relay de-energise : b;
  */
  char cmd = data[0];

  // There is an issue with the compiler :-
  // If you declare a variable with a case
  // the code hangs and will never progress 
  // to later cases.
  int ms;
  int speed;
  int val;
  
  // Switch on command type
  switch (cmd) {
    
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
    case 's':
      // Parse out the speed
      speed = parse_int(data, 2);
      // Set as current speed
      current_speed = speed;
      Serial.print("Speed;");
      break;

    case 'a':
      digitalWrite(RLY_PIN, LOW);
      Serial.print("RlyOn;");
      break;

    case 'b':
      digitalWrite(RLY_PIN, HIGH);
      Serial.print("RlyOff;");
      break;

    case 'h':
      if (!go_home_or_max(HOME)) {
        Serial.print("Motor fault;");
      };
      Serial.print("Home;");
      break;

    case 'x':
      if (!go_home_or_max(MAX)) {
        Serial.print("Motor fault;");
      }
      Serial.print("Max;");
      break;

    case 'p':
      Serial.print("Pos: ");
      Serial.print(get_feedback_value());
      Serial.print(';');
      break;

    case 'f':
      if (move_ms(20, FORWARD)) {
        Serial.print("NudgeFwd;");
      } else {
        Serial.println("Motor fault on nudge!;");
      }
      break;

    case 'r':
      if (move_ms(20, REVERSE)) {
        Serial.print("NudgeRev;");
      } else {
        Serial.print("Motor fault on nudge!;");
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

    case 'v':
      // Parse out the number of ms
      ms = parse_int(data, 2);

      if (move_ms(ms, REVERSE)) {
        Serial.print("msRev;");
      } else {
        Serial.print("Motor fault on reverse ms!;");
      }
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

    case 'm':
      // Parse out the value to move to
      val = parse_int(data, 2);
      
      if (move_to_feedback_value(val)) {
        Serial.print("MoveTo: ");
        Serial.print(val);
        Serial.print(';');
      } else {
        Serial.print("Motor fault on move!;");
      }
      break;

    default:
      Serial.print("Bad cmd!;");
  }
}

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

int check_abort() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil(';');
    if (data[0] == 'z') {
      return TRUE;
    }
  }
  return FALSE;
}

int check_stop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil(';');
    if (data[0] == 'e') {
      return TRUE;
    }
  }
  return FALSE;
}

int check_limit() {
  // Test for end of travel
  last_fb_val = fb_val;
  fb_val = get_feedback_value();
  if (((fb_val + 2) >= last_fb_val) && ((fb_val - 2) <= last_fb_val)) {
    // Possibly at end stop
    if (fb_counter-- <= 0) {
      // Feedback stationary ish for 5 counts
      return TRUE; 
    }
  }
  return FALSE;
}

// Get current feedback pot value (0-1023)
int get_feedback_value() {
  return analogRead(POTENTIOMETER_PIN);
}

// Move to home or max position
int go_home_or_max(int pos) {
  // Assume home is reverse

  // Local vars
  int fb_val = -1;
  int last_fb_val = -1;
  int fb_counter = 5;
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
      // Test for end of travel
      last_fb_val = fb_val;
      fb_val = get_feedback_value();
      //p[0] = fb_val;
      //p[1] = last_fb_val;
      //debug_print("Pass: ", 2, p);
      if (((fb_val + 2) >= last_fb_val) && ((fb_val - 2) <= last_fb_val)) {
        // Possibly at end stop
        if (fb_counter-- <= 0) {
          // Feedback stationary ish for 5 counts
          break; 
        }
      }
      // Time for a status report?
      if (st_counter-- <= 0) {
        st_counter = 5;
        Serial.print("Status: ");
        Serial.print(get_feedback_value());
        Serial.print(";");
      }
      // Check for user abort
      if (check_abort()) {
        md.setM1Speed(0);
        break;
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
    Serial.print("Status: ");
    Serial.print(get_feedback_value());
    Serial.print(";");
    if (dir == FORWARD) {
      while(get_feedback_value() < target) {
        if (counter-- <= 0) {
          counter = 5;
          Serial.print("Status: ");
          Serial.print(get_feedback_value());
          Serial.print(";");
          if (check_abort()) {
            md.setM1Speed(0);
            return TRUE;
          }
        }
        delay(100);
      }
    } else {
      while(get_feedback_value() > target){
        if (counter-- <= 0) {
          counter = 5;
          Serial.print("Status: ");
          Serial.print(get_feedback_value());
          Serial.print(";");
          if (check_abort()) {
            md.setM1Speed(0);
            return TRUE;
          }
        }
        delay(100);
      }
    }
    // See how close we got
    md.setM1Speed(0);
    delay(500);
    int diff = abs(get_feedback_value() - target);
    //p[0] = diff;
    //p[1] = get_feedback_value();
    //p[2] = target;
    //debug_print("Diff1: ", 3, p);
    int l_speed = current_speed;
    if (diff > 1) {
      // More than about 0.2% deviation
      // See if we can do better
      current_speed = 100;  // slow it down
      int attempts = 10;    // Limit this at 10 correction attempts
      int dir;

      // Ensure we take up gear slack in the same direction on every move.
      // If necessary move reverse so adjustment is always moving forward.
      while(get_feedback_value() > target) {
        move_ms(100, REVERSE);
      }

      while (diff > 1) {
        if (get_feedback_value() > target) {
          dir = REVERSE;
        } else {
          dir = FORWARD;
        }
        move_ms(50, dir);
        diff = abs(get_feedback_value() - target);
        //p[0] = diff;
        //p[1] = get_feedback_value();
        //p[2] = target;
        //debug_print("Diff2: ", 3, p);
        if (attempts -- <= 0) {
          break;
        }
      }
    }

    // Stop driving
    current_speed = l_speed;
    md.setM1Speed(0);
    // Final position update
    delay(500);
    Serial.print("Status: ");
          Serial.print(get_feedback_value());
          Serial.print(";");
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
    Serial.print("Status: ");
    Serial.print(get_feedback_value());
    Serial.print(";");
  }
  return TRUE;
}

int move_fwd() {
  int counter = 5;
  // Set the limit switch counter
  fb_counter = 5;
  md.setM1Speed(current_speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    while (!check_stop() && !check_limit()) {
      delay (100);
      if (counter-- <= 0) {
        counter = 5;
        Serial.print("Status: ");
        Serial.print(get_feedback_value());
        Serial.print(";");
      }
    }
  }
  md.setM1Speed(0);
  return TRUE;
}

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
        Serial.print("Status: ");
        Serial.print(get_feedback_value());
        Serial.print(";");
      }
    }
  }
  md.setM1Speed(0);
  return TRUE;
}

int stop_move() {
  md.setM1Speed(0);
  return TRUE;
}

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
