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

// Instance of motor driver
DualMC33926MotorShield md;
int current_speed = 250; // Current speed in range 0 to +-400

// Setup runs once on startup
void setup() {
  // We use a simple text serial protocol between RPi and ourselves
  Serial.begin(9600);
  // Initialise motor driver
  md.init();
  pinMode(POTENTIOMETER_PIN, INPUT);
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
  *   o Set speed (slow, medium, fast) : s,s[m][f].;
  *   o Move to home position : h;
  *   o Move to max extension : x;
  *   o Get position value : p;
  *   o Move to position : m,pos as int [0 to 1023].;
  *   o Nudge forward : f;
  *   o Nudge reverse : r;
  *   o Run forward for n ms : w,n[ms].;
  *   o Run reverse for n ms : v,n[ms].;
  */
  char cmd = data[0];
  int ms;

  // Switch on command type
  switch (cmd) {
    case 's':
      Serial.print("Set speed;");
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
      };
      Serial.print("Max;");
      break;

    case 'p':
      Serial.print("Pos: ");
      Serial.print(get_feedback_value());
      Serial.print(';');
      break;

    case 'f':
      if (move_ms(100, FORWARD)) {
        Serial.print("Nudge fwd;");
      } else {
        Serial.println("Motor fault on nudge!;");
      }
    break;

    case 'r':
      if (move_ms(100, REVERSE)) {
        Serial.print("Nudge rev;");
      } else {
        Serial.print("Motor fault on nudge!;");
      }
      break;
    
    case 'w':
      // Parse out the number of ms
      ms = parse_int(data, 2);

      if (move_ms(ms, FORWARD)) {
        Serial.print("Moved ms forward;");
      } else {
        Serial.print("Motor fault on forward ms!;");
      }
      break;

    case 'v':
      // Parse out the number of ms
      ms = parse_int(data, 2);

      if (move_ms(ms, REVERSE)) {
        Serial.print("Moved ms reverse;");
      } else {
        Serial.print("Motor fault on reverse ms!;");
      }
      break;
      
    case 'm':
      // Parse out the value to move to
      int val = parse_int(data, 2);
      
      if (move_to_feedback_value(val)) {
        Serial.print("Moved to ");
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

// Get current feedback pot value (0-1023)
int get_feedback_value() {
  return analogRead(POTENTIOMETER_PIN);
}

// Move to home or max position
int go_home_or_max(int pos) {
  // Assume home is reverse
  int speed;
  if (pos == HOME) {
    speed = -current_speed;
  } else {
    speed = current_speed;
  }
  md.setM1Speed(speed);
  if (md.getFault()) {
    md.setM1Speed(0);
    return FALSE;
  } else {
    // We wait until the feedback no longer changes.
    // This means we have hit the limit switch and movement has stopped.
    int last_val = -1;
    delay(200);
    while (get_feedback_value() != last_val) {
      //Serial.print("Status: ");
      //Serial.print(get_feedback_value());
      //Serial.print(";");
      last_val = get_feedback_value();
      delay(500);
    }
    delay(100);
    md.setM1Speed(0);
    return TRUE;
  }
}

// Move actuator to given feedback value
int move_to_feedback_value(int target) {
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
    if (dir == FORWARD) {
      while(get_feedback_value() < target) {
        delay(500);
      }
    } else {
      while(get_feedback_value() > target){
        delay(500);
      }
    }
    // Stop driving
    md.setM1Speed(0);
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
  }
  return TRUE;
}
