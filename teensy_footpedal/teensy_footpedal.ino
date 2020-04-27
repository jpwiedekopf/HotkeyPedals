#define STATE_DISENGAGED 0
#define STATE_ENGAGED 1
#define THRESHOLD 400
#define POLLING_RATE 10
#define DEBOUNCE_PERIOD 10 // one activation each DEBOUNCE_PERIOD * POLLING_RATE ms
#define IDLE_RATE 100
#define KEEPALIVE_MESSAGE "."
#define LEFT_MESSAGE "l"
#define RIGHT_MESSAGE "r"

int pinLeftPedal = A4;
int pinRightPedal = A0;
int stateLeft = STATE_DISENGAGED;
int stateRight = STATE_DISENGAGED;
int valueLeft = 0;
int valueRight = 0;
int prevValueLeft = 0;
int prevValueRight = 0;
int timerLeft = 0;
int timerRight = 0;
int timerIdle = IDLE_RATE;

void setup() {
  Serial.begin(9600);
}

void loop() {
  prevValueLeft = valueLeft;
  prevValueRight = valueRight;
  valueLeft = analogRead(pinLeftPedal);
  valueRight = analogRead(pinRightPedal);
  
  switch (stateLeft) {
    case STATE_DISENGAGED:
      if (valueLeft != 0 && valueLeft < THRESHOLD && prevValueLeft >= THRESHOLD) {
        fireLeft();
        stateLeft = STATE_ENGAGED;
        timerLeft = DEBOUNCE_PERIOD;
        timerIdle = IDLE_RATE;
      }
      break;
    case STATE_ENGAGED:
      timerLeft--;
      if (timerLeft == 0) {
        stateLeft = STATE_DISENGAGED;
      }
      break;
  }

  switch (stateRight) {
    case STATE_DISENGAGED:
      if (valueRight != 0 && valueRight < THRESHOLD && prevValueRight >= THRESHOLD) {
        fireRight();
        stateRight = STATE_ENGAGED;
        timerRight = DEBOUNCE_PERIOD;
        timerIdle = IDLE_RATE;
      }
      break;
    case STATE_ENGAGED:
      timerRight--;
      if (timerRight == 0) {
        stateRight = STATE_DISENGAGED;
      }
      break;
  }

  timerIdle -= 1;
  if (timerIdle <= 0) {
    timerIdle = IDLE_RATE;
    Serial.print(KEEPALIVE_MESSAGE);
  }
  
  delay(POLLING_RATE);
}

void fireLeft() {
  Serial.print(LEFT_MESSAGE);
}

void fireRight() {
  Serial.print(RIGHT_MESSAGE);
}
