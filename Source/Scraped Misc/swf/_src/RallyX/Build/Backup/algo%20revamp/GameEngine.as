package classes.game {
	
	import flash.display.Sprite;
	import flash.display.MovieClip;
	import flash.events.Event;
	import flash.events.KeyboardEvent;
	import classes.events.GameEvent;
	import classes.events.ScreenEvent;
	import classes.game.Hero;
	import classes.game.Hud;
	import classes.game.Background;
	import classes.control.GlobalControl;
	import classes.control.GameControl;
	import flash.media.Sound;
	import com.greensock.TweenMax;
	
	public class GameEngine extends Sprite{
		
		// Constants
		public static const LEFT_ARROW:int = 37;
		public static const RIGHT_ARROW:int = 39;
		public static const DOWN_ARROW:int = 40;
		public static const UP_ARROW:int = 38;
		private const SPACE_KEY:int = 32;
		
		// Private Properties
		private var _gameStarted:Boolean;
		private var _speedX:Number;
		private var _speedY:Number;
		private var _keyDown:int;
		
		private var _clipper:Sprite;
		private var _callToAction:MovieClip;
		private var _cta2:MovieClip;
		private var _lifeUpAnim:MovieClip;
		private var _background:Background;
		private var _hero:Hero;
		private var _hud:Hud;
		private var _distortionField:MovieClip;
		private var _crashSnd:Sound;
		private var _safeSnd:Sound;
		private var _pickupSnd:Sound;
		private var _allKeysGathered:Boolean;
		
		// Constructor
		public function GameEngine() {
			_clipper = new ArbitrarySprite();
			_callToAction = new CallToAction();
			_cta2 = new CTAKeys();
			_background = new Background();
			_hero = new Hero();
			_hud = new Hud();
			_lifeUpAnim = new LifeUpAnim();
			_distortionField = new DistortionField();
			_safeSnd = new SafeSND();
			_crashSnd = new CrashSND();
			_pickupSnd = new PickupSND();
			_allKeysGathered = false;
			_gameStarted = false;
			_keyDown = -1;
			
			_callToAction.refParent = this;
			_callToAction.gotoAndStop(1);
			
			_lifeUpAnim.gotoAndStop(1);
			_lifeUpAnim.refParent = this;
			_lifeUpAnim.visible = false;
			
			_distortionField.gotoAndStop(1);
			_distortionField.refParent = this;
			_distortionField.visible = false;
			
			_cta2.refParent = this;
			_cta2.gotoAndStop(1);
			_cta2.visible = false;
			
			_hero.x = 375;
			_hero.y = 200;
			_hero.addEventListener(GameEvent.LOSE_LIFE, onLoseLife);
			
			_clipper.width = 600;
			_clipper.height = 450;
			
			_background.mask = _clipper;
			_background.addEventListener(GameEvent.WIN_LEVEL, onWin);
			_background.addEventListener(GameEvent.GOT_KEY, onGotKey);
			_background.addEventListener(GameEvent.HIT_WALL, onHitWall);
			_background.addEventListener(GameEvent.GOT_ALL_KEYS, onGotAllKeys);
			
			_hud.addEventListener(GameEvent.LIFE_UP, onLifeUp);
			_hud.addEventListener(GameEvent.LOSE_LIFE, onLoseLife);
			
			addChild (_background);
			addChild (_clipper);
			addChild (_hero);
			addChild (_callToAction);
			addChild (_cta2);
			addChild (_lifeUpAnim);
			addChild (_distortionField);
			addChild (_hud);
		}
		
		// Public Methods
		public function init():void{
			var _map:XML = GlobalControl._maps[GameControl._gameLevel-1];
			_hero.init();
			_background.init(_hero);
			_hud.init(int(_map.@rows), int(_map.@cols), int(_map.init.border.@width));
			_hud.registerElements(_hero, _background.getKeyList(), _background.getEnemyList(), int(_map.init.secure_zone.@r), int(_map.init.secure_zone.@c));
			_speedY =  GameControl.SPEEDY;
			_speedX = 0;
			_hero.faceNorth();
			_allKeysGathered = false;
			_gameStarted = false;
			_keyDown = -1;
		}
		
		public function startGame():void{
			this.stage.addEventListener(Event.ENTER_FRAME, onFrame);
			this.stage.addEventListener(KeyboardEvent.KEY_DOWN, onKeyPress);
			this.stage.addEventListener(KeyboardEvent.KEY_UP, onKeyRelease);
			this.stage.focus = this.stage;
			_callToAction.gotoAndPlay(1);
		}
		
		public function cleanUp():void{			
			_background.cleanUp();
			_lifeUpAnim.gotoAndStop(1);
			_lifeUpAnim.visible = false;
			_callToAction.gotoAndStop(1);
			_hud.clearElements();
		}
		
		// Internal Public Methods
		public function onCTAEnd():void{
			_callToAction.visible = false;
			_gameStarted = true;
		}
		
		public function lifeUpAnimDone():void{
			_lifeUpAnim.visible = false;
			_lifeUpAnim.gotoAndStop(1);
		}
		
		public function distorted():void{
			nextLife();
			_distortionField.gotoAndPlay("endDistortion");
		}
		
		public function distortionDone():void{
			_distortionField.visible = false;
			if (_allKeysGathered){
				_cta2.gotoAndStop(1);
				_cta2.visible = true;
				_cta2.play();
			}else{
				_callToAction.gotoAndStop(1);
				_callToAction.visible = true;
				_callToAction.play();
			}
		}
		
		public function onCTA2Done():void{
			_cta2.visible = false;
			_cta2.gotoAndStop(1);
			if (!_gameStarted){
				_gameStarted = true;
			}
		}
		
		
		// Private Methods
		private function resetLevelVariables():void{
			_callToAction.visible = true;
			_callToAction.gotoAndStop(1);
		}
		
		private function onFrame(e:Event):void{
			if (!_gameStarted){
				return;
			}
			var _repDir:int = _background.updatePositions(_speedX, _speedY, _keyDown);
			if (_repDir == _keyDown){
				setDirection();
			}
			_hud.updateMap();
			_hud.updateGas(_hero.empActive);
		}
		
		private function onKeyPress(e:KeyboardEvent):void{
			if (_gameStarted){
				if (e.keyCode == LEFT_ARROW){
					_keyDown = LEFT_ARROW;
				}else if (e.keyCode == RIGHT_ARROW){
					_keyDown = RIGHT_ARROW;
				}else if (e.keyCode == DOWN_ARROW){
					_keyDown = DOWN_ARROW;
				}else if (e.keyCode == UP_ARROW){
					_keyDown = UP_ARROW;
				}else if (e.keyCode == SPACE_KEY){
					_hero.setEmp(true);
				}
				attemptDirectionChange();
			}
		}
		
		private function onKeyRelease(e:KeyboardEvent):void{
			if (e.keyCode == SPACE_KEY){
				_hero.setEmp(false);
			}else if ((e.keyCode == LEFT_ARROW) && (_keyDown == LEFT_ARROW)){
				_keyDown = -1;
			}else if ((e.keyCode == RIGHT_ARROW) && (_keyDown == RIGHT_ARROW)){
				_keyDown = -1;
			}else if ((e.keyCode == DOWN_ARROW) && (_keyDown == DOWN_ARROW)){
				_keyDown = -1;
			}else if ((e.keyCode == UP_ARROW) && (_keyDown == UP_ARROW)){
				_keyDown = -1;
			}
		}
		
		private function setDirection():void{
			if (_keyDown == UP_ARROW){
				goNorth();
			}else if (_keyDown == DOWN_ARROW){
				goSouth();
			}else if (_keyDown == LEFT_ARROW){
				goWest();
			}else if (_keyDown == RIGHT_ARROW){
				goEast();
			}
		}
		
		private function attemptDirectionChange():void{
			
		}
		
		private function onGotKey(e:GameEvent):void{
			_pickupSnd.play();
			_hud.updateScore(ZoneKey(e._data));
		}
		
		private function onHitWall(e:GameEvent):void{
			if (_speedY > 0){
				if (_background.checkEast()){
					goEast();
				}else if (_background.checkWest()){
					goWest();
				}else {
					goSouth();
				}
			}else if (_speedX < 0){
				if (_background.checkSouth()){
					goSouth();
				}else if (_background.checkNorth()){
					goNorth();
				}else {
					goWest();
				}
			}else if (_speedY<0){
				 if (_background.checkWest()){
					goWest();
				}else if (_background.checkEast()){
					goEast();
				}else {
					goNorth();
				}
			}else {
				if (_background.checkNorth()){
					goNorth();
				}else if (_background.checkSouth()){
					goSouth();
				}else {
					goEast();
				}
			}
		}
		
		private function goNorth():void{
			_speedY =  GameControl.SPEEDY;
			_speedX = 0;
			_hero.faceNorth();
		}
		
		private function goEast():void{
			_hero.faceEast();
			_speedX = -1*GameControl.SPEEDX;
			_speedY = 0;
		}
		
		private function goSouth():void{
			_speedY = -1* GameControl.SPEEDY;
			_speedX = 0;
			_hero.faceSouth();
		}
		
		private function goWest():void{
			_hero.faceWest();
			_speedX = GameControl.SPEEDX;
			_speedY = 0;
		}
		
		private function onWin(e:GameEvent):void{
			_safeSnd.play();
			_gameStarted = false;
			_speedX = 0;
			_speedY = 0;
			
			this.stage.removeEventListener(Event.ENTER_FRAME, onFrame);
			this.stage.removeEventListener(KeyboardEvent.KEY_DOWN, onKeyPress);
			this.stage.removeEventListener(KeyboardEvent.KEY_UP, onKeyRelease);
			GameControl._empBonus = GameControl._empLevel;
			dispatchEvent(new GameEvent(GameEvent.WIN_LEVEL));
		}
		
		private function onLoseLife(e:GameEvent):void{
			_crashSnd.play();
			_gameStarted = false;
			_speedX = 0;
			_speedY = 0;
			GameControl._lives--;
			if (GameControl._lives == -1){
				gameOver();
			}else{
				_distortionField.visible = true;
				_distortionField.gotoAndPlay("startDistortion");
			}
		}
		
		private function onLifeUp(e:GameEvent):void{
			_lifeUpAnim.visible = true;
			_lifeUpAnim.gotoAndPlay(1);
		}
		
		private function onGotAllKeys(e:GameEvent):void{
			_allKeysGathered = true;
			_cta2.visible = true;
			_cta2.gotoAndPlay(1);
		}
		
		private function gameOver():void{
			this.stage.removeEventListener(Event.ENTER_FRAME, onFrame);
			this.stage.removeEventListener(KeyboardEvent.KEY_DOWN, onKeyPress);
			this.stage.removeEventListener(KeyboardEvent.KEY_UP, onKeyRelease);
			GameControl._empBonus = 0;
			dispatchEvent(new GameEvent(GameEvent.LOSE_LEVEL));
		}
		
		private function nextLife():void{
			GameControl.resetLifeVariables();
			_hud.updateLife();
			_hud.resetLifeVariables();
			_speedY =  GameControl.SPEEDY;
			_speedX = 0;
			_hero.faceNorth();
			_background.resetLevel();
			_lifeUpAnim.gotoAndStop(1);
			_lifeUpAnim.visible = false;
		}
		
		

	}// Class
}// Package