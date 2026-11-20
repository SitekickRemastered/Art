using System.Collections.Generic;
using Unity.VectorGraphics;
using UnityEngine;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
	/// A scrollable grid of every chip. Clicking one shows its effect on the
	/// Sitekick; clicking it again removes only that effect, so any number of
	/// chips can be on at once.
	/// </summary>
	public class ChipGallery : MonoBehaviour
	{
		[System.Serializable]
		public class Entry
		{
			public int id;
			public Sprite icon;
			public GameObject effect;
			public ChipData.EffectLayer layer;
		}

		[SerializeField]
		protected RectTransform content;

		[SerializeField]
		protected Transform sitekick;

		[SerializeField]
		protected float effectScale = 0.2f;

		[SerializeField]
		protected List<Entry> entries = new List<Entry>();

		protected sealed class Item
		{
			public SVGImage icon;
		}

		protected readonly Dictionary<int, Item> items = new Dictionary<int, Item>();
		protected readonly Dictionary<int, GameObject> spawned = new Dictionary<int, GameObject>();

		protected bool built;

		public int EntryCount { get { return entries != null ? entries.Count : 0; } }

		public IList<Entry> Entries { get { return entries; } }

		public Transform Sitekick { get { return sitekick; } }

		public IEnumerable<GameObject> ActiveEffects { get { return spawned.Values; } }

		public int ActiveCount { get { return spawned.Count; } }

		void Start()
		{
			Build();
		}

		/// <summary>Creates one button per chip. Called on start; safe to call again.</summary>
		public void Build()
		{
			if ( built || content == null )
				return;

			built = true;

			for ( int i = content.childCount - 1; i >= 0; i-- )
				Kill( content.GetChild( i ).gameObject );

			foreach ( var entry in entries )
			{
				var go = new GameObject( "chip_" + entry.id.ToString( "0000" ) );
				var rect = go.AddComponent<RectTransform>();
				rect.SetParent( content, false );

				// the chips are vector sprites (SVG tessellated at import), so the
				// grid draws them with an SVGImage instead of a textured Image
				var image = go.AddComponent<SVGImage>();
				image.sprite = entry.icon;
				image.preserveAspect = true;
				image.raycastTarget = true;
				if ( entry.icon == null )
					image.color = new Color( 1f, 1f, 1f, 0.15f );

				var button = go.AddComponent<Button>();
				button.targetGraphic = image;
				button.transition = Selectable.Transition.None; // the tint below is the feedback

				int id = entry.id;
				button.onClick.AddListener( () => Toggle( id ) );

				items[ id ] = new Item { icon = image };
			}
		}

		/// <summary>Turns the chip's effect on, or off when it is already on.</summary>
		public void Toggle( int id )
		{
			var entry = Find( id );
			if ( entry == null )
				return;

			if ( spawned.TryGetValue( id, out var running ) && running != null )
			{
				Kill( running );
				spawned.Remove( id );
				Tint( id, false );
				return;
			}

			spawned.Remove( id );

			var parent = LayerOf( entry.layer );
			if ( parent == null || entry.effect == null )
				return;

			var instance = Instantiate( entry.effect, parent );
			instance.name = "Chip_" + id.ToString( "0000" ) + "_Effect";
			instance.transform.localPosition = Vector3.zero;
			instance.transform.localRotation = Quaternion.identity;
			instance.transform.localScale = Vector3.one * effectScale;

			spawned[ id ] = instance;
			Tint( id, true );
		}

		public void ClearAll()
		{
			foreach ( var pair in spawned )
			{
				if ( pair.Value != null )
					Kill( pair.Value );
				Tint( pair.Key, false );
			}

			spawned.Clear();
		}

		protected Entry Find( int id )
		{
			for ( int i = 0; i < entries.Count; i++ )
			{
				if ( entries[ i ].id == id )
					return entries[ i ];
			}

			return null;
		}

		/// <summary>The Sitekick child that holds this effect layer.</summary>
		protected Transform LayerOf( ChipData.EffectLayer layer )
		{
			if ( sitekick == null )
				return null;

			foreach ( var effectLayer in sitekick.GetComponentsInChildren<EffectLayer>( true ) )
			{
				if ( effectLayer.layer == layer )
					return effectLayer.transform;
			}

			return sitekick;
		}

		/// <summary>Dims the icon while its effect is showing.</summary>
		protected void Tint( int id, bool active )
		{
			if ( !items.TryGetValue( id, out var item ) || item.icon == null )
				return;

			item.icon.color = active ? new Color( 0.5f, 0.5f, 0.5f, 1f ) : Color.white;
		}

		protected static void Kill( GameObject go )
		{
			if ( go == null )
				return;

			if ( Application.isPlaying )
				Object.Destroy( go );
			else
				Object.DestroyImmediate( go );
		}
	}
}
