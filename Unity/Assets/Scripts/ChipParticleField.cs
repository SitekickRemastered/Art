using System;
using System.Collections.Generic;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// A spawned particle effect: the stream `corus/effects/FlakeMC` starts.
	///
	/// Some effects never use a timeline.  Chip 151's `effect_000151.onTimer`
	/// adds `Math.random() * 10` flakes a second and each `FlakeMC` runs its own
	/// `init()`: a random x across the 375 px stage, `y = -25` (25 px above it),
	/// `scaleX = scaleY = Math.random()`, then a linear tween of `y` to
	/// `stageHeight + 25` over `3 + Math.random() * 5` s.  `BubbleMC` (chips 152
	/// and 153) is the same with the ends swapped: it starts below the stage and
	/// rises.  The flake's own 128-frame symbol keeps playing while it falls, at
	/// the movie's frame rate, so a particle is a moving picture, not a still.
	///
	/// The importer cannot port a random field into a prefab, so it bakes four
	/// copies on fixed x columns with fixed fall times and one still frame -- a
	/// stand-in that says where the group sits but has a quarter of the density,
	/// no size variation and no animation.  This component is the real thing:
	/// it hides those stand-ins on its first update (so a held, authored pose is
	/// still what `ChipPlayCheck --hold` measures) and spawns from the SWF rule.
	///
	/// The data comes from the export (`Tools/SwfToSvg/build_particle_fields.py`
	/// writes `art`, `rising`, `frameRate` and the spawn rate into the prefab
	/// from `Sprites/chip_XXXX_effect.json`), so a re-export keeps it.
	/// </summary>
	public class ChipParticleField : MonoBehaviour
	{
		[Serializable]
		public class Art
		{
			[Tooltip( "The importer's node name, e.g. particle_0." )]
			public string name;

			[Tooltip( "BubbleMC spawns below the stage and rises; FlakeMC falls." )]
			public bool rising;

			[Tooltip( "Every exported frame of the particle's symbol, in order." )]
			public Sprite[ ] frames;
		}

		[Tooltip( "The particle symbols this effect spawns, from its effect json." )]
		[SerializeField]
		protected Art[ ] art = new Art[ 0 ];

		[Tooltip( "effect_NNNNN.onStaged starts new Timer(1000): the burst is once a second." )]
		[SerializeField]
		protected float spawnInterval = 1f;

		[Tooltip( "onTimer spawns int(Math.random() * 10) particles per tick: 0..9, mean 4.5." )]
		[SerializeField]
		protected int spawnBurst = 10;

		[Tooltip( "FlakeMC tweens over 3 + int(Math.random() * 6) s: 3..8 whole seconds." )]
		[SerializeField]
		protected float minLifetime = 3f;

		[SerializeField]
		protected float maxLifetime = 8f;

		[Tooltip( "The effect's SWF stage, in the pixels the art is drawn in." )]
		[SerializeField]
		protected float stageWidth = 375f;

		[SerializeField]
		protected float stageHeight = 300f;

		[Tooltip( "How far past the stage a particle starts and ends." )]
		[SerializeField]
		protected float margin = 25f;

		[Tooltip( "The symbol's frames play at the movie's frame rate." )]
		[SerializeField]
		protected float frameRate = 31f;

		[Tooltip( "Upper bound on live particles; the pool reuses the oldest." )]
		[SerializeField]
		protected int capacity = 96;

		/// <summary>One SWF pixel in the effect's own units (`build_prefabs.U`).</summary>
		public const float UnitsPerSwfPixel = 0.01735f;

		protected sealed class Live
		{
			public Transform transform;
			public SpriteRenderer renderer;
			public Art art;
			public float born;
			public float life;
			public float x;
			public float from;
			public float to;
			public float scale;
			public Vector2 offset;
			public bool active;
		}

		protected readonly List<Live> pool = new List<Live>( );
		protected Transform host;
		protected bool started;
		protected float tick;

		public int Capacity { get { return capacity; } }

		/// <summary>The effect's SWF stage, in SWF px: the domain the rule draws in.</summary>
		public float StageWidth { get { return stageWidth; } }
		public float StageHeight { get { return stageHeight; } }
		public int LiveCount { get { var n = 0; foreach ( var p in pool ) if ( p.active ) n++; return n; } }
		public int ArtCount { get { return art != null ? art.Length : 0; } }

		/// <summary>
		/// Each live particle's spawn x, in SWF px from the stage centre.
		///
		/// The spread of the stream is a property of these values, not of the
		/// capture: blob detection merges particles (`FlakeMC` art overlaps), so a
		/// merged pair or a missed one at the edge moves the measured extremes.
		/// </summary>
		public float[ ] LiveX( )
		{
			var xs = new List<float>( );
			foreach ( var p in pool )
				if ( p.active )
					xs.Add( p.x );
			return xs.ToArray( );
		}

		protected void Update( )
		{
			if ( art == null || art.Length == 0 )
				return;

			if ( !started )
			{
				// Deferred to the first update on purpose: the check that measures a
				// spawned effect disables this component in the frame the effect is
				// instantiated, and the authored pose it reads must still be there.
				started = true;
				HideAuthored( );
			}

			var now = Time.time;

			// onTimer fires on a 1 s Timer and adds a random 0..9 flakes, so the
			// stream is a burst a second rather than a smooth drip
			tick += Time.deltaTime;
			while ( tick >= spawnInterval )
			{
				tick -= spawnInterval;
				var burst = UnityEngine.Random.Range( 0, Mathf.Max( 1, spawnBurst ) );
				for ( var i = 0; i < burst; i++ )
					Spawn( now );
			}

			foreach ( var p in pool )
			{
				if ( !p.active )
					continue;

				var t = ( now - p.born ) / p.life;
				if ( t >= 1f )
				{
					Retire( p );
					continue;
				}

				p.transform.localPosition = new Vector3( p.x * UnitsPerSwfPixel,
					Mathf.Lerp( p.from, p.to, t ) * UnitsPerSwfPixel ) + (Vector3)( p.offset * p.scale );
				p.transform.localScale = new Vector3( p.scale, p.scale, 1f );

				var frames = p.art.frames;
				if ( frames != null && frames.Length > 1 )
				{
					// each particle runs its own playhead, as its clip does in Flash
					var frame = (int)( ( now - p.born ) * frameRate ) % frames.Length;
					if ( frames[ frame ] != null )
						p.renderer.sprite = frames[ frame ];
				}
			}
		}

		/// <summary>Stops the baked stand-ins: the four fixed columns and their clips.</summary>
		protected void HideAuthored( )
		{
			host = FindHost( );
			foreach ( var animator in GetComponentsInChildren<Animator>( true ) )
			{
				if ( IsAuthored( animator.gameObject.name ) )
					animator.enabled = false;
			}

			foreach ( var tr in GetComponentsInChildren<Transform>( true ) )
			{
				if ( tr != transform && IsAuthored( tr.gameObject.name ) )
					tr.gameObject.SetActive( false );
			}
		}

		static bool IsAuthored( string name )
		{
			// "particle_0".."particle_3" and their "sprite" children; a spawned
			// copy is named "particle_spawn_N", which must not match
			if ( !name.StartsWith( "particle_", StringComparison.Ordinal ) )
				return false;
			var rest = name.Substring( "particle_".Length );
			return rest.Length > 0 && char.IsDigit( rest[ 0 ] );
		}

		Transform FindHost( )
		{
			// the extras node already carries the stage offset, so a particle's
			// local position is plain `x_swf * U` from the stage centre
			foreach ( var tr in GetComponentsInChildren<Transform>( true ) )
			{
				if ( tr.name.EndsWith( "_extras", StringComparison.Ordinal ) )
					return tr;
			}
			return transform;
		}

		protected void Spawn( float now )
		{
			// the SWF picks a symbol per spawn; a chip with several alternates
			// them the way the builder stacked them
			var pick = art[ UnityEngine.Random.Range( 0, art.Length ) ];
			if ( pick == null || pick.frames == null || pick.frames.Length == 0 )
				return;

			var live = Take( );
			var half = stageWidth * 0.5f;
			var reach = stageHeight * 0.5f + margin;
			var rising = pick.rising;

			live.art = pick;
			live.born = now;
				live.life = UnityEngine.Random.Range( Mathf.RoundToInt( minLifetime ),
				Mathf.RoundToInt( maxLifetime ) + 1 );
			// FlakeMC: x = Math.random() * stageWidth, measured from the stage's
			// left edge, i.e. -187.5..+187.5 from its centre
			live.x = -half + UnityEngine.Random.value * stageWidth;
			// local y is up: FlakeMC starts 25 px above the stage and falls, BubbleMC
			// starts 25 px below it and rises
			live.from = rising ? -reach : reach;
			live.to = -live.from;
			live.scale = UnityEngine.Random.value;
			live.offset = OffsetOf( pick );
			live.active = true;

			live.transform.SetParent( host, false );
			live.transform.localPosition = new Vector3( live.x * UnitsPerSwfPixel, live.from * UnitsPerSwfPixel );
			live.transform.localScale = new Vector3( live.scale, live.scale, 1f );
			live.renderer.sprite = pick.frames[ 0 ];
			live.renderer.enabled = true;
		}

		/// <summary>Where the authored sprite child sits, so a spawn stays centred.</summary>
		Vector2 OffsetOf( Art pick )
		{
			foreach ( var tr in GetComponentsInChildren<Transform>( true ) )
			{
				if ( tr.name != pick.name )
					continue;
				foreach ( var child in tr.GetComponentsInChildren<Transform>( true ) )
				{
					if ( child.name == "sprite" )
						return child.localPosition;
				}
			}
			return Vector2.zero;
		}

		Live Take( )
		{
			foreach ( var p in pool )
			{
				if ( !p.active )
					return p;
			}

			if ( pool.Count < capacity )
			{
				var go = new GameObject( "particle_spawn_" + pool.Count );
				var sr = go.AddComponent<SpriteRenderer>( );
				sr.enabled = false;
				sr.sortingLayerID = 0;
				sr.sortingOrder = 0;
				var template = Template( );
				if ( template != null )
				{
					sr.sharedMaterial = template.sharedMaterial;
					sr.sortingLayerID = template.sortingLayerID;
					sr.sortingOrder = template.sortingOrder;
				}
				var p = new Live { transform = go.transform, renderer = sr };
				pool.Add( p );
				return p;
			}

			// full: reuse the oldest one rather than dropping the spawn
			var oldest = pool[ 0 ];
			foreach ( var p in pool )
				if ( p.born < oldest.born )
					oldest = p;
			oldest.active = false;
			return oldest;
		}

		SpriteRenderer Template( )
		{
			foreach ( var r in GetComponentsInChildren<SpriteRenderer>( true ) )
			{
				if ( IsAuthored( r.gameObject.name ) || IsAuthored( r.transform.parent != null ? r.transform.parent.name : "" ) )
					return r;
			}
			return null;
		}

		void Retire( Live p )
		{
			// stay under the extras node: a retired copy is hidden, not moved to the
			// scene root, so the pool never leaves stray objects behind
			p.active = false;
			p.renderer.enabled = false;
		}
	}
}
